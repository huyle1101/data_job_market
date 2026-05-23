import os
import re
import time
import json
import pandas as pd
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime
start_time = datetime.now()

load_dotenv()

API_KEYS = [
    os.getenv('API_KEY_01'),
    os.getenv('API_KEY_02'),
    os.getenv('API_KEY_03'),
    os.getenv('API_KEY_04'),
    os.getenv('API_KEY_05'),
    os.getenv('API_KEY_06'),
]
API_KEYS = [key for key in API_KEYS if key] 

current_key_idx = 0
client = genai.Client(api_key=API_KEYS[current_key_idx])

# MODEL ROTATION

MODEL_LIST = [
    os.getenv('MODEL_01'),
    os.getenv('MODEL_02'),
    os.getenv('MODEL_03'),
    os.getenv('MODEL_04'),
    os.getenv('MODEL_05'),
]
print(f"Model list ({len(MODEL_LIST)}): {MODEL_LIST}")

current_model_idx = 0

def rotate_model() -> bool:
    """Rotate to next model. Returns False if a full cycle was completed."""
    global current_model_idx
    next_idx = (current_model_idx + 1) % len(MODEL_LIST)
    if next_idx == 0:
        current_model_idx = next_idx
        return False
    current_model_idx = next_idx
    return True

def current_model_label() -> str:
    return f"{MODEL_LIST[current_model_idx]} [{current_model_idx + 1}/{len(MODEL_LIST)}]"

INPUT_JSON = "test/careerviet/raw_data/careerviet_20260523_143910.json" 
OUTPUT_CSV = "test/careerviet/processed_data/careerviet_20260523_143910.csv"

BATCH_SIZE = 10          # Number of job profiles per API call (full extraction)
RELEVANCE_BATCH_SIZE = 20  # Larger batch for relevance check (lighter prompt)
MAX_RETRIES = 5            # Max retries before skipping a batch

# SCHEMA DEFINITION
OUTPUT_FIELDS = [
    "is_data_relevant",
    "job_url", "company_name", "title", "job_category", "employment_type",
    "position_level", "education_level", "raw_address", "city", "district",
    "min_salary_vnd", "max_salary_vnd", "is_salary_negotiable",
    "min_experience_years", "max_experience_years",
    # Benefits
    "raw_benefits_list",
    "has_insurance", "has_premium_insurance", "has_bonus", "has_allowance",
    "has_annual_leave", "has_travel", "has_training", "has_health_check",
    "has_device_provided",
    "extracted_skills", "error_log"
]

# Columns that already exist in raw data — Gemini will VERIFY their content is correct
# before passing through to output. Only flat string/simple fields qualify.
VERIFY_FROM_RAW = [
    "job_url", "company_name", "title", "job_category",
    "employment_type", "position_level", "raw_address",
]

# Columns that must always be extracted by Gemini (never pre-filled from raw)
EXTRACT_ONLY = [
    "is_data_relevant",
    "education_level", "city", "district",
    "min_salary_vnd", "max_salary_vnd", "is_salary_negotiable",
    "min_experience_years", "max_experience_years",
    "raw_benefits_list",
    "has_insurance", "has_premium_insurance", "has_bonus", "has_allowance",
    "has_annual_leave", "has_travel", "has_training", "has_health_check",
    "has_device_provided",
    "extracted_skills", "error_log",
]

def switch_api_key():
    """Rotate to next API key when a quota limit (429) is hit."""
    global current_key_idx, client
    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
    client = genai.Client(api_key=API_KEYS[current_key_idx])
    print(f"    🔄 Rotated to API Key #{current_key_idx + 1}")

def build_relevance_prompt(profiles: list[dict]) -> str:
    """Lightweight prompt to check is_data_relevant only."""
    blocks = []
    for i, p in enumerate(profiles):
        blocks.append(
            f"=== PROFILE_{i} ===\n"
            f"Title: {p.get('title', '')}\n"
            f"Job Category: {p.get('job_category', '')}\n"
            f"Position Level: {p.get('position_level', '')}\n"
            f"Requirements & Description (first 500 chars): "
            f"{str(p.get('job_requirements', ''))[:500]}"
        )

    return f"""You are classifying job postings.
Below are {len(profiles)} job postings separated by "=== PROFILE_N ===".

For EACH profile, decide if the role's PRIMARY function is data-focused.
Return EXACTLY ONE JSON array of {len(profiles)} objects, each with a single key:
- is_data_relevant (boolean)

TRUE: Data Engineer, Data Analyst, Data Scientist, BI Developer, ETL Developer,
      Analytics Engineer, ML Engineer, Database Administrator, Data Architect,
      Data Warehouse, Business Intelligence, AI/ML roles with heavy data work.
FALSE: Backend Developer, Frontend Developer, DevOps, QA, Marketing, Sales,
       Product Manager, HR, Finance — even if they occasionally use data tools.
When in doubt, lean FALSE.

Rules:
- Return raw JSON array only, no markdown.
- Order must match PROFILE_0, PROFILE_1, etc.

{''.join(chr(10) + b for b in blocks)}
"""


def check_relevance_batch(profiles: list[dict]) -> list[bool]:
    """
    Step 1: Call Gemini to check is_data_relevant only.
    Returns a list of booleans matching profiles order.
    Falls back to True on error (so full extraction still runs).
    """
    prompt = build_relevance_prompt(profiles)
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            _current_model = MODEL_LIST[current_model_idx]
            response = client.models.generate_content(
                model=_current_model,
                contents=prompt,
                config=config,
            )
            raw = response.text.strip()
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON array in relevance response.")
            parsed = json.loads(match.group())
            if len(parsed) != len(profiles):
                raise ValueError(f"Expected {len(profiles)} items, got {len(parsed)}")
            return [bool(item.get("is_data_relevant", True)) for item in parsed]

        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err
            is_500   = "500" in err or "503" in err or "INTERNAL" in err or "UNAVAILABLE" in err

            if is_quota:
                print(f"    ⚠️ Relevance check — 429, rotating key...")
                switch_api_key()
                time.sleep(2)
            elif is_500:
                rotated = rotate_model()
                if rotated:
                    print(f"    🔄 Relevance check — 503, rotated to: {current_model_label()}")
                else:
                    wait_time = 5 * (2 ** attempt)
                    print(f"    ⚠️ Relevance check — full model cycle, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    attempt += 1
            else:
                print(f"    ⚠️ Relevance check failed: {err[:100]} — defaulting all to True")
                return [True] * len(profiles)

    print(f"    ⚠️ Relevance check max retries — defaulting all to True")
    return [True] * len(profiles)


def build_batch_prompt(profiles: list[dict]) -> str:
    """Constructs the prompt for a batch of job profiles.

    Each profile dict may include a 'pre_filled' key — a dict of fields already
    present in the raw data. Gemini will VERIFY those values are correct for their
    column and EXTRACT everything else.
    """
    blocks = []
    for i, p in enumerate(profiles):
        pre_filled_section = ""
        if p.get("pre_filled"):
            lines = "\n        ".join(
                f"{k}: {v}" for k, v in p["pre_filled"].items()
            )
            pre_filled_section = f"\n        --- PRE-FILLED (verify only) ---\n        {lines}"

        raw_text = f"""
        Title: {p.get('title', '')}
        Job Category: {p.get('job_category', '')}
        Employment Type: {p.get('employment_type', '')}
        Position Level: {p.get('position_level', '')}
        Salary Text: {p.get('salary', '')}
        Experience Text: {p.get('experience', '')}
        Location Text: {p.get('location', '')}
        Benefits Text: {p.get('benefits', '')}
        Other Info: {p.get('other_information', '')}
        Requirements & Description: {p.get('job_requirements', '')}
        {pre_filled_section}
        """
        blocks.append(f"=== PROFILE_{i} ===\n{raw_text.strip()}")

    prompt = f"""You are a Data Engineer building a Star Schema Data Warehouse.
Below are {len(profiles)} raw job postings separated by "=== PROFILE_N ===".

For each profile, some fields may be marked as "PRE-FILLED (verify only)".
- For PRE-FILLED fields: check if the value is correct and appropriate for that column name.
  If correct, return the same value. If wrong or mismatched, return the corrected value.
- For all other fields: extract from the raw text.

Extract/verify the information for EACH profile and return EXACTLY ONE JSON Array containing {len(profiles)} objects.
Each object MUST have the following keys:

- is_data_relevant (boolean): Read ALL available fields (title, job category, position level,
  employment type, salary, experience, location, benefits, other info, requirements & description)
  holistically and set to true if the role's PRIMARY function is data-focused.
  TRUE examples: Data Engineer, Data Analyst, Data Scientist, BI Developer, ETL Developer,
  Analytics Engineer, ML Engineer, Database Administrator, Data Architect, Data Platform,
  Data Warehouse, Business Intelligence, AI/ML roles with heavy data work.
  FALSE examples: Backend Developer, Frontend Developer, DevOps, QA, Marketing, Sales,
  Product Manager, HR, Finance — even if they occasionally use data tools.
  When in doubt, lean FALSE: only mark TRUE if data is clearly the core responsibility.
- job_url (string or null): Verified or extracted job URL.
- company_name (string or null): Verified or extracted company name.
- title (string or null): Verified or extracted job title.
- job_category (string or null): Verified or extracted job category.
- employment_type (string or null): Verified or extracted employment type (e.g. "Toàn thời gian").
- position_level (string or null): Verified or extracted position/seniority level.
- education_level (string or null): Extracted from 'Other Info' (e.g., "Đại học").
- raw_address (string or null): Location field may be a list or string. Extract the most 
  meaningful address element (longest, contains street/ward/district/city info). 
  Ignore single characters or short codes. Return as a clean string, or null if none found.
- city (string or null): Standardized full official city or province name extracted from 
  any available field. Covers all Vietnamese provinces and cities, not limited to major ones.
- district (string or null): Standardized full official district name extracted from any 
  available field. Covers all Vietnamese districts, not limited to urban ones.
- min_salary_vnd (number or null): Convert string like "12 Tr" to 12000000.
- max_salary_vnd (number or null): Convert string like "25 Tr" to 25000000.
- is_salary_negotiable (boolean): true if salary says "Cạnh tranh" or "Thỏa thuận", otherwise false.
- min_experience_years (number or null): Extract minimum years of experience.
- max_experience_years (number or null): Extract maximum years of experience.
- raw_benefits_list (string or null): Full raw benefits text as extracted, preserving original wording.
- has_insurance (boolean): true if benefits mention BHXH/BHYT/bảo hiểm bắt buộc (mandatory state insurance).
- has_premium_insurance (boolean): true if benefits mention voluntary/premium health insurance (PVI, Bảo Việt, PTI, bảo hiểm sức khỏe tự nguyện...).
- has_bonus (boolean): true if benefits mention bonus/thưởng (thưởng 13, KPI, lễ tết, performance bonus...).
- has_allowance (boolean): true if benefits mention allowances/phụ cấp (cơm trưa, đi lại, xăng xe, điện thoại, nhà ở...).
- has_annual_leave (boolean): true if benefits mention annual leave/nghỉ phép năm.
- has_travel (boolean): true if benefits mention company trips/du lịch/teambuilding.
- has_training (boolean): true if benefits mention training/đào tạo/cấp ngân sách học tập/learning budget.
- has_health_check (boolean): true if benefits mention periodic health checkup/khám sức khỏe định kỳ.
- has_device_provided (boolean): true if benefits mention laptop/macbook/máy tính/thiết bị được cung cấp.
- extracted_skills (array of strings): Extract ALL skills mentioned in any field, including:
  + Technical: languages, tools, platforms, frameworks, methodologies, concepts
  + Soft skills: interpersonal, communication, management, thinking abilities
  + Certifications and qualifications
  Extract the exact term as written in the text. Return [] if none found.

Rules:
- If data is missing for a field, use null.
- Do NOT output any markdown blocks (like ```json), just the raw JSON array.
- The order of objects must match PROFILE_0, PROFILE_1, etc.

{''.join(chr(10) + b for b in blocks)}
"""
    return prompt

# Configuration to force JSON output
config = types.GenerateContentConfig(
    temperature=0.1,
    response_mime_type="application/json",
    thinking_config=types.ThinkingConfig(thinking_budget=0)
)

def process_batch(profiles: list[dict]) -> list[dict]:
    """Calls the Gemini API with key + model rotation and error handling."""
    empty_result = lambda: {f: None for f in OUTPUT_FIELDS}
    fallback = [empty_result() for _ in profiles]
    prompt = build_batch_prompt(profiles)

    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            _current_model = MODEL_LIST[current_model_idx]
            response = client.models.generate_content(
                model=_current_model,
                contents=prompt,
                config=config,
            )
            raw = response.text.strip()

            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                raise ValueError("JSON array not found in response.")

            parsed = json.loads(match.group())
            if len(parsed) != len(profiles):
                raise ValueError(f"Expected {len(profiles)} items, got {len(parsed)}")

            results = []
            for item in parsed:
                clean = empty_result()
                for key in item:
                    if key in clean:
                        clean[key] = item[key]
                results.append(clean)
            return results

        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err
            is_500   = "500" in err or "503" in err or "INTERNAL" in err or "UNAVAILABLE" in err

            if is_quota:
                print(f"    ⚠️ Rate limit (429) — rotating API key...")
                switch_api_key()
                time.sleep(2)
                # Do NOT increment attempt — key rotation is free

            elif is_500:
                # Rotate model first; only sleep + increment if full cycle exhausted
                rotated = rotate_model()
                if rotated:
                    print(f"    🔄 503/500 overload — rotated to model: {current_model_label()}")
                else:
                    wait_time = 5 * (2 ** attempt)
                    print(f"    ⚠️ 503/500 — full model cycle exhausted "
                          f"(attempt {attempt + 1}/{MAX_RETRIES}), waiting {wait_time}s...")
                    time.sleep(wait_time)
                    attempt += 1

            else:
                print(f"    ❌ Batch failed: {err[:150]}")
                for r in fallback:
                    r["error_log"] = f"ERROR: {err[:100]}"
                return fallback

    print(f"    ❌ Max retries reached ({MAX_RETRIES}). Skipping batch.")
    for r in fallback:
        r["error_log"] = "ERROR: max retries exceeded"
    return fallback

def main():
    # 1. Load input data
    if os.path.exists(OUTPUT_CSV):
        # If output CSV exists, resume from it
        df = pd.read_csv(OUTPUT_CSV)
        print(f"📂 Found existing {OUTPUT_CSV}. Resuming pipeline...")
    else:
        # UPDATED: If starting fresh, read from the JSON file
        try:
            df = pd.read_json(INPUT_JSON)
            print(f"📂 Starting fresh from JSON: {INPUT_JSON}.")
        except Exception as e:
            print(f"❌ Failed to load JSON file: {e}")
            return
            
    total = len(df)

    # 2. Initialize missing OUTPUT columns in the DataFrame
    for f in OUTPUT_FIELDS:
        if f not in df.columns:
            df[f] = None if f != "extracted_skills" else pd.Series(dtype='object')

    # Helper: a cell is considered "has value" if it is not NaN/None/empty-string
    def has_value(val) -> bool:
        if val is None:
            return False
        try:
            if pd.isna(val):
                return False
        except (TypeError, ValueError):
            pass
        return str(val).strip() != ""

    # 3. SMART AUTO-RESUME LOGIC
    # A row is "fully processed" if all EXTRACT_ONLY cols (except error_log) have values
    # AND there is no error_log entry.
    extract_required = [c for c in EXTRACT_ONLY if c != "error_log"]
    processed_mask = df[extract_required].notna().all(axis=1) & df["error_log"].isna()

    # Get indices of rows that are NOT processed (missing extracted data or have errors)
    todo_indices = df.index[~processed_mask].tolist()
    total_batches = (len(todo_indices) + BATCH_SIZE - 1) // BATCH_SIZE

    if not todo_indices:
        print("✅ All rows are fully processed. Nothing to do!")
        return

    print(f"📋 Need to process: {len(todo_indices)} rows ({total_batches} batches)")

    start_time = datetime.now()

    # 4. Step 1 — Relevance check (large batches, lightweight prompt)
    print(f"\n🔍 Step 1: Relevance check ({len(todo_indices)} rows, "
          f"batch_size={RELEVANCE_BATCH_SIZE})...")
    relevance_map = {}  # idx -> bool
    rel_batches = list(range(0, len(todo_indices), RELEVANCE_BATCH_SIZE))
    for rb_num, chunk_start in enumerate(rel_batches, 1):
        chunk_idx = todo_indices[chunk_start: chunk_start + RELEVANCE_BATCH_SIZE]
        profiles_rel = []
        for idx in chunk_idx:
            row = df.loc[idx]
            profiles_rel.append({
                "idx":              idx,
                "title":            row.get("title", ""),
                "job_category":     row.get("job_category", ""),
                "position_level":   row.get("position", ""),
                "job_requirements": row.get("job_requirements", ""),
            })
        print(f"  Relevance batch {rb_num}/{len(rel_batches)} "
              f"| key #{current_key_idx + 1} | {current_model_label()}")
        flags = check_relevance_batch(profiles_rel)
        for profile, flag in zip(profiles_rel, flags):
            relevance_map[profile["idx"]] = flag

    relevant_indices = [i for i in todo_indices if relevance_map.get(i, True)]
    skipped = len(todo_indices) - len(relevant_indices)
    print(f"  ✅ Relevance done: {len(relevant_indices)} relevant, "
          f"{skipped} skipped (is_data_relevant=False)")

    # Mark skipped rows in the DataFrame immediately
    for idx in todo_indices:
        if not relevance_map.get(idx, True):
            df.at[idx, "is_data_relevant"] = False

    total_batches = (len(relevant_indices) + BATCH_SIZE - 1) // BATCH_SIZE

    if not relevant_indices:
        print("\n✅ No relevant rows to extract. Saving and exiting.")
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        return

    # 5. Step 2 — Full extraction (only relevant rows)
    print(f"\n⚙️  Step 2: Full extraction ({len(relevant_indices)} rows, "
          f"batch_size={BATCH_SIZE})...")

    for batch_num, chunk_start in enumerate(range(0, len(relevant_indices), BATCH_SIZE), 1):
        chunk_idx = relevant_indices[chunk_start: chunk_start + BATCH_SIZE]
        profiles = []

        for idx in chunk_idx:
            row = df.loc[idx]

            # Build pre_filled: VERIFY_FROM_RAW cols that already have a value in the df
            # (either carried over from raw JSON or a previous partial run)
            pre_filled = {}
            for col in VERIFY_FROM_RAW:
                # Check both the OUTPUT col and its raw-source equivalent
                raw_source = {"job_url": "url", "position_level": "position",
                              "raw_address": "location"}.get(col, col)
                val = row.get(col) if has_value(row.get(col)) else row.get(raw_source)
                if has_value(val):
                    pre_filled[col] = val

            profiles.append({
                "idx":               idx,
                "title":             row.get("title", ""),
                "job_category":      row.get("job_category", ""),
                "employment_type":   row.get("employment_type", ""),
                "position_level":    row.get("position", ""),
                "salary":            row.get("salary", ""),
                "experience":        str(row.get("experience", "")),
                "location":          str(row.get("location", "")),
                "benefits":          str(row.get("benefits", "")),
                "job_requirements":  row.get("job_requirements", ""),
                "other_information": row.get("other_information", ""),
                "pre_filled":        pre_filled,
            })

        print(f"⏳ Batch {batch_num}/{total_batches} | key #{current_key_idx + 1} | {current_model_label()}")
        results = process_batch(profiles)

        # 6. Map AI results back to the DataFrame
        for profile, result in zip(profiles, results):
            idx = profile["idx"]

            # Write all Gemini-returned fields (verified + extracted)
            df.at[idx, "is_data_relevant"] = True
            for field, value in result.items():
                if field == "is_data_relevant":
                    continue
                elif field == "error_log":
                    if value:
                        df.at[idx, "error_log"] = value
                    elif pd.notna(df.at[idx, "error_log"]):
                        df.at[idx, "error_log"] = None
                else:
                    df.at[idx, field] = value

        # 7. Save checkpoint after every extraction batch
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"  ✅ Saved checkpoint to {OUTPUT_CSV}")
        
        # Slight delay to avoid hitting RPM limits too aggressively
        time.sleep(2) 

    elapsed = datetime.now() - start_time
    print(f"\n🎉 Done! Total Time: {elapsed}")
    
    # 7. Final Statistics
    df_out = pd.read_csv(OUTPUT_CSV)
    errors = df_out["error_log"].notna().sum()
    print("── Final Statistics ──")
    if errors > 0:
        print(f"⚠️ {errors} rows failed. Run the script again to auto-retry them.")
    else:
        end_time = datetime.now()
        total_time = end_time - start_time
        print(f"✅ 100% Complete! Data is ready, total time: {total_time}")

if __name__ == "__main__":
    main()