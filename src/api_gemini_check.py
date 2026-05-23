import os
import re
import json
import time
import pandas as pd
from datetime import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# CONFIG
INPUT_CSV = "test/careerviet/processed_data/careerviet_20260523_143910.csv"

API_KEYS = [k for k in [os.getenv(f"API_KEY_{i:02d}") for i in range(1, 7)] if k]
MODEL_LIST = [m for m in [os.getenv(f"MODEL_{i:02d}") for i in range(1, 6)] if m]

print(f"API keys loaded  : {len(API_KEYS)}")
print(f"Model list ({len(MODEL_LIST)}): {MODEL_LIST}")

current_key_idx   = 0
current_model_idx = 0
client = genai.Client(api_key=API_KEYS[current_key_idx])

VERIFY_BATCH_SIZE = 10    # rows per Gemini verification call
MAX_RETRIES       = 5    # max retry attempts before giving up on a batch
SPOT_CHECK_N      = 3    # rows to print in spot-check sections

# Gemini generation config — low temperature for deterministic extraction
config = types.GenerateContentConfig(
    temperature=0.1,
    response_mime_type="application/json",
    thinking_config=types.ThinkingConfig(thinking_budget=0)
)

# SCHEMA
# Fields originally extracted by Gemini — these are what we verify / re-extract
VERIFY_FIELDS = [
    "education_level",
    "city", "district",
    "min_salary_vnd", "max_salary_vnd", "is_salary_negotiable",
    "min_experience_years", "max_experience_years",
    "has_laptop", "has_insurance", "has_annual_leave", "has_training", "has_travel",
    "extracted_skills",
]

OUTPUT_FIELDS = [
    "is_data_relevant",
    "job_url", "company_name", "title", "job_category", "employment_type",
    "position_level", "education_level", "raw_address", "city", "district",
    "min_salary_vnd", "max_salary_vnd", "is_salary_negotiable",
    "min_experience_years", "max_experience_years", "has_laptop",
    "has_insurance", "has_annual_leave", "has_training", "has_travel",
    "extracted_skills", "error_log",
]

BOOLEAN_FIELDS = [
    "is_data_relevant", "is_salary_negotiable",
    "has_laptop", "has_insurance", "has_annual_leave", "has_training", "has_travel",
]

NUMERIC_FIELDS = [
    "min_salary_vnd", "max_salary_vnd",
    "min_experience_years", "max_experience_years",
]

STRING_FIELDS = [
    "job_url", "company_name", "title", "job_category", "employment_type",
    "position_level", "education_level", "raw_address", "city", "district",
]


# API / MODEL ROTATION
def switch_api_key():
    """Rotate to the next API key (called on 429 / RESOURCE_EXHAUSTED)."""
    global current_key_idx, client
    current_key_idx = (current_key_idx + 1) % len(API_KEYS)
    client = genai.Client(api_key=API_KEYS[current_key_idx])
    print(f"    🔄 Rotated to API key #{current_key_idx + 1}")


def rotate_model() -> bool:
    """
    Rotate to the next model in MODEL_LIST (called on 500 / 503).
    Returns False if a full cycle was completed (all models tried).
    """
    global current_model_idx
    next_idx = (current_model_idx + 1) % len(MODEL_LIST)
    if next_idx == 0:
        current_model_idx = next_idx
        return False   # full cycle completed
    current_model_idx = next_idx
    return True


def current_model_label() -> str:
    return f"{MODEL_LIST[current_model_idx]} [{current_model_idx + 1}/{len(MODEL_LIST)}]"


# DISPLAY HELPERS
def sep(title=""):
    line = "═" * 60
    if title:
        print(f"\n{line}\n  {title}\n{line}")
    else:
        print(line)


def bar(filled, total, width=20):
    pct = filled / total * 100 if total else 0
    b = "█" * int(pct / (100 / width))
    return f"{filled:>4}/{total}  ({pct:5.1f}%)  {b}"


# LOAD CSV
def load_csv(path: str) -> pd.DataFrame:
    sep("1. LOAD CSV")
    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        raise SystemExit(1)

    df = pd.read_csv(path, dtype=str)   # read all as str first for header-dedup check
    print(f"📂 Loaded {len(df)} rows from {path}")
    print(f"📋 Columns ({len(df.columns)}): {list(df.columns)}")

    # Remove duplicate header rows (rows whose values equal the column names)
    dup_mask = df.apply(lambda r: r.eq(df.columns).all(), axis=1)
    if dup_mask.any():
        print(f"🧹 Removed {dup_mask.sum()} duplicate header row(s).")
        df = df[~dup_mask].reset_index(drop=True)
    else:
        print("✅ No duplicate header rows.")

    # Add is_verified tracking column if this is the first run
    if "is_verified" not in df.columns:
        df["is_verified"] = None
        print("ℹ️  Added 'is_verified' column for resume tracking.")

    # Cast numeric fields
    for col in NUMERIC_FIELDS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cast boolean fields (including is_verified)
    def _to_bool(v):
        s = str(v).strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
        return None

    for col in BOOLEAN_FIELDS + ["is_verified"]:
        if col in df.columns:
            df[col] = df[col].map(_to_bool)

    return df


# PROMPT BUILDERS
def build_verify_prompt(profiles: list[dict]) -> str:
    """
    Build a verification prompt that asks Gemini to check each row's
    extracted values against its raw text columns.
    """
    blocks = []
    for i, p in enumerate(profiles):
        extracted_str = "\n".join(
            f"  {f}: {p['extracted'].get(f)}"
            for f in VERIFY_FIELDS
        )
        blocks.append(
            f"=== PROFILE_{i} ===\n"
            f"Job Description     : {str(p.get('job_description',  ''))[:800]}\n"
            f"Job Requirements    : {str(p.get('job_requirements', ''))[:800]}\n"
            f"Other Information   : {str(p.get('other_information',''))[:500]}\n\n"
            f"Extracted Values:\n{extracted_str}"
        )

    fields_list = "\n".join(f"  - {f}" for f in VERIFY_FIELDS)

    return f"""You are a data quality auditor for a job data warehouse.
Below are {len(profiles)} job postings separated by "=== PROFILE_N ===".
Each profile shows the raw text and previously extracted field values.

For EACH profile, verify whether the extracted values are correct based on the raw text.
Return EXACTLY ONE JSON array of {len(profiles)} objects, each with:
  - is_correct (boolean): true if ALL fields are correctly extracted.
  - corrections (object): if is_correct is false, include ONLY the incorrect fields
    mapped to their correct values. If is_correct is true, use an empty object {{}}.
    IMPORTANT: if is_correct is false, corrections MUST contain at least one field.

Fields to verify:
{fields_list}

Verification rules:
  - education_level     : match the degree requirement mentioned (e.g. "Đại học", "Cao đẳng"). null if absent.
  - city / district     : match the work location stated in the raw text.
  - min_salary_vnd      : numeric VND value (e.g. "12 Tr" → 12000000). null if not stated.
  - max_salary_vnd      : numeric VND value. null if not stated.
  - is_salary_negotiable: true if salary text contains "Cạnh tranh", "Thỏa thuận", or equivalent.
  - min_experience_years: numeric minimum years of experience. null if not stated.
  - max_experience_years: numeric maximum years of experience. null if not stated.
  - has_laptop          : true only if benefits explicitly mention laptop or MacBook.
  - has_insurance       : true only if benefits explicitly mention insurance / bảo hiểm.
  - has_annual_leave    : true only if benefits explicitly mention annual leave / nghỉ phép.
  - has_training        : true only if benefits explicitly mention training / đào tạo.
  - has_travel          : true only if benefits explicitly mention travel / du lịch.
  - extracted_skills    : list of all technical and soft skills found in the raw text.

Rules:
  - Return raw JSON array only — no markdown, no code fences.
  - Array order must match PROFILE_0, PROFILE_1, etc.

{"".join(chr(10) + b for b in blocks)}
"""


def build_reextract_prompt(profiles: list[dict]) -> str:
    """
    Build a full re-extraction prompt for rows whose verification failed.
    Uses only the raw text columns available in the CSV.
    """
    blocks = []
    for i, p in enumerate(profiles):
        blocks.append(
            f"=== PROFILE_{i} ===\n"
            f"Title              : {p.get('title', '')}\n"
            f"Job Category       : {p.get('job_category', '')}\n"
            f"Employment Type    : {p.get('employment_type', '')}\n"
            f"Position Level     : {p.get('position_level', '')}\n"
            f"Raw Address        : {p.get('raw_address', '')}\n"
            f"Job Description    : {str(p.get('job_description',  ''))[:1000]}\n"
            f"Job Requirements   : {str(p.get('job_requirements', ''))[:1000]}\n"
            f"Other Information  : {str(p.get('other_information',''))[:600]}"
        )

    return f"""You are a Data Engineer building a Star Schema Data Warehouse.
Below are {len(profiles)} raw job postings separated by "=== PROFILE_N ===".

Extract information for EACH profile and return EXACTLY ONE JSON array of {len(profiles)} objects.
Each object MUST have the following keys:

  - education_level      (string or null) : Required education level (e.g. "Đại học", "Cao đẳng"). null if absent.
  - city                 (string or null) : Standardized city name (e.g. "Hà Nội", "Hồ Chí Minh"). null if absent.
  - district             (string or null) : Standardized district name. null if absent.
  - min_salary_vnd       (number or null) : Min salary in VND ("12 Tr" → 12000000). null if not stated.
  - max_salary_vnd       (number or null) : Max salary in VND ("25 Tr" → 25000000). null if not stated.
  - is_salary_negotiable (boolean)        : true if salary is "Cạnh tranh", "Thỏa thuận", or equivalent.
  - min_experience_years (number or null) : Minimum years of experience required. null if not stated.
  - max_experience_years (number or null) : Maximum years of experience required. null if not stated.
  - has_laptop           (boolean)        : true if benefits mention laptop or MacBook.
  - has_insurance        (boolean)        : true if benefits mention insurance / bảo hiểm.
  - has_annual_leave     (boolean)        : true if benefits mention annual leave / nghỉ phép.
  - has_training         (boolean)        : true if benefits mention training / đào tạo.
  - has_travel           (boolean)        : true if benefits mention travel / du lịch.
  - extracted_skills     (array of str)   : All technical and soft skills found. Return [] if none.

Rules:
  - Use null for any field where data is missing or cannot be determined.
  - Do NOT output markdown code fences — return raw JSON array only.
  - Array order must match PROFILE_0, PROFILE_1, etc.

{"".join(chr(10) + b for b in blocks)}
"""


# GEMINI CALLER (shared, with full rotation + retry)
def call_gemini(prompt: str, expected_count: int) -> list[dict] | None:
    """
    Send a prompt to Gemini with API key rotation (429) and model rotation (500/503).
    Returns the parsed JSON list on success, or None after MAX_RETRIES failures.
    """
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            response = client.models.generate_content(
                model=MODEL_LIST[current_model_idx],
                contents=prompt,
                config=config,
            )
            raw = response.text.strip()

            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in response.")

            parsed = json.loads(match.group())
            if len(parsed) != expected_count:
                raise ValueError(
                    f"Expected {expected_count} items, got {len(parsed)}"
                )
            return parsed

        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err
            is_500   = "500" in err or "503" in err or "INTERNAL" in err or "UNAVAILABLE" in err

            if is_quota:
                print(f"    ⚠️ Rate limit (429) — rotating API key...")
                switch_api_key()
                time.sleep(2)
                # Key rotation is free — do NOT increment attempt counter

            elif is_500:
                rotated = rotate_model()
                if rotated:
                    print(f"    🔄 503/500 overload — rotated to: {current_model_label()}")
                else:
                    wait_time = 5 * (2 ** attempt)
                    print(
                        f"    ⚠️ 503/500 — full model cycle exhausted "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}), waiting {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    attempt += 1

            else:
                print(f"    ❌ API call failed: {err[:150]}")
                attempt += 1

    return None   # exhausted all retries


# GEMINI VERIFICATION + AUTO RE-EXTRACTION
def run_verification(df: pd.DataFrame) -> pd.DataFrame:
    sep("2. GEMINI FIELD VERIFICATION + AUTO RE-EXTRACTION")

    # Resume logic: skip rows that are already verified or not relevant
    verify_mask = (
        (df["is_data_relevant"] == True) &
        (df["is_verified"] != True) &
        (df["error_log"].isna())
    )
    todo_indices = df.index[verify_mask].tolist()

    if not todo_indices:
        print("✅ All relevant rows are already verified. Skipping verification step.")
        return df

    total_batches = (len(todo_indices) + VERIFY_BATCH_SIZE - 1) // VERIFY_BATCH_SIZE
    print(
        f"📋 Rows to verify: {len(todo_indices)} "
        f"({total_batches} batches, batch_size={VERIFY_BATCH_SIZE})"
    )

    start_time = datetime.now()
    passed      = 0
    corrected   = 0
    reextracted = 0
    failed      = 0

    for batch_num, chunk_start in enumerate(
        range(0, len(todo_indices), VERIFY_BATCH_SIZE), 1
    ):
        chunk_idx = todo_indices[chunk_start: chunk_start + VERIFY_BATCH_SIZE]

        # Build profile dicts for the verification prompt
        profiles = []
        for idx in chunk_idx:
            row = df.loc[idx]
            profiles.append({
                "idx":             idx,
                "job_description":  str(row.get("job_description",  "")),
                "job_requirements": str(row.get("job_requirements", "")),
                "other_information": str(row.get("other_information", "")),
                # Contextual fields used only if full re-extraction is needed
                "title":           str(row.get("title",          "")),
                "job_category":    str(row.get("job_category",   "")),
                "employment_type": str(row.get("employment_type","")),
                "position_level":  str(row.get("position_level", "")),
                "raw_address":     str(row.get("raw_address",    "")),
                # Current extracted values to be verified
                "extracted": {f: row.get(f) for f in VERIFY_FIELDS if f in df.columns},
            })

        print(
            f"\n⏳ Verification batch {batch_num}/{total_batches} "
            f"| key #{current_key_idx + 1} | {current_model_label()}"
        )

        # ── Phase A: verify ────────────────────────────────────────────────────
        verdicts = call_gemini(build_verify_prompt(profiles), len(profiles))

        if verdicts is None:
            # Verification API call failed entirely — log error and continue
            print(f"    ❌ Verification failed for batch {batch_num} — logging errors.")
            for p in profiles:
                df.at[p["idx"], "error_log"] = "ERROR: verification API call failed"
            failed += len(profiles)
            df.to_csv(INPUT_CSV, index=False, encoding="utf-8-sig")
            continue

        # ── Phase B: process verdicts ──────────────────────────────────────────
        needs_reextract = []   # profiles where corrections were not provided

        for profile, verdict in zip(profiles, verdicts):
            idx         = profile["idx"]
            is_correct  = bool(verdict.get("is_correct", False))
            corrections = verdict.get("corrections") or {}

            if is_correct:
                # All fields verified as correct
                df.at[idx, "is_verified"] = True
                passed += 1

            elif corrections:
                # Apply Gemini-supplied field corrections directly
                for field, value in corrections.items():
                    if field in df.columns:
                        # df.at[] không gán được list trực tiếp
                        if isinstance(value, list):
                            df.at[idx, field] = json.dumps(value, ensure_ascii=False)
                        else:
                            df.at[idx, field] = value
                df.at[idx, "is_verified"] = True
                corrected += 1
                print(f"    ✏️  idx={idx} — corrected: {list(corrections.keys())}")

            else:
                # is_correct=False but no corrections supplied — queue for full re-extraction
                needs_reextract.append(profile)

        # ── Phase C: full re-extraction for rows with no corrections ───────────
        if needs_reextract:
            print(f"    🔁 Re-extracting {len(needs_reextract)} row(s) from raw text...")
            re_results = call_gemini(
                build_reextract_prompt(needs_reextract), len(needs_reextract)
            )

            if re_results is None:
                print(f"    ❌ Re-extraction failed — logging errors.")
                for p in needs_reextract:
                    df.at[p["idx"], "error_log"] = "ERROR: re-extraction API call failed"
                failed += len(needs_reextract)
            else:
                for profile, result in zip(needs_reextract, re_results):
                    idx = profile["idx"]
                    for field in VERIFY_FIELDS:
                        if field in result and field in df.columns:
                            value = result[field]
                            if isinstance(value, list):
                                df.at[idx, field] = json.dumps(value, ensure_ascii=False)
                            else:
                                df.at[idx, field] = value
                    df.at[idx, "is_verified"] = True
                    # Clear any previous error after successful re-extraction
                    df.at[idx, "error_log"] = None
                    reextracted += 1

        # Checkpoint save after every batch so progress survives interruption
        df.to_csv(INPUT_CSV, index=False, encoding="utf-8-sig")
        elapsed = datetime.now() - start_time
        print(
            f"    ✅ Checkpoint saved | batch {batch_num}/{total_batches} | "
            f"elapsed={elapsed} | "
            f"passed={passed}  corrected={corrected}  "
            f"re-extracted={reextracted}  failed={failed}"
        )

        time.sleep(1)   # small pause to respect RPM limits

    sep()
    print("Verification summary:")
    print(f"  ✅ Passed (no changes needed) : {passed}")
    print(f"  ✏️  Corrected in-place         : {corrected}")
    print(f"  🔁 Fully re-extracted          : {reextracted}")
    print(f"  ❌ Failed (logged in error_log): {failed}")

    return df


# IS_DATA_RELEVANT DISTRIBUTION
def check_relevance(df: pd.DataFrame):
    sep("3. IS_DATA_RELEVANT DISTRIBUTION")
    total = len(df)

    if "is_data_relevant" not in df.columns:
        print("⚠️  Column 'is_data_relevant' not found.")
        return

    n_true  = (df["is_data_relevant"] == True).sum()
    n_false = (df["is_data_relevant"] == False).sum()
    n_null  = df["is_data_relevant"].isna().sum()

    print(f"  TRUE  (relevant)   : {bar(n_true,  total)}")
    print(f"  FALSE (irrelevant) : {bar(n_false, total)}")
    print(f"  NULL  (unprocessed): {bar(n_null,  total)}")

    # Spot-check FALSE rows — verify they are not misclassified
    false_rows = df[df["is_data_relevant"] == False]
    if not false_rows.empty:
        sample = false_rows.sample(min(SPOT_CHECK_N, len(false_rows)), random_state=42)
        print(f"\n🔍 Spot-check {len(sample)} FALSE rows (verify not misclassified):")
        for idx, row in sample.iterrows():
            print(f"\n  idx={idx}")
            print(f"    title        : {row.get('title', '')}")
            print(f"    job_category : {row.get('job_category', '')}")
            print(f"    position     : {row.get('position_level', '')}")

    # Spot-check TRUE rows — verify they are correctly classified
    true_rows = df[df["is_data_relevant"] == True]
    if not true_rows.empty:
        sample = true_rows.sample(min(SPOT_CHECK_N, len(true_rows)), random_state=7)
        print(f"\n🔍 Spot-check {len(sample)} TRUE rows (verify correctly classified):")
        for idx, row in sample.iterrows():
            print(f"\n  idx={idx}")
            print(f"    title        : {row.get('title', '')}")
            print(f"    job_category : {row.get('job_category', '')}")
            print(f"    position     : {row.get('position_level', '')}")


# EXTRACTION QUALITY (True rows only)
def check_extraction_quality(df: pd.DataFrame):
    sep("4. EXTRACTION QUALITY  (is_data_relevant=True rows only)")

    relevant = df[df["is_data_relevant"] == True]
    total = len(relevant)

    if total == 0:
        print("⚠️  No rows with is_data_relevant=True found.")
        return

    print(f"Checking {total} relevant rows:\n")

    null_100 = []
    extract_fields = [f for f in OUTPUT_FIELDS if f not in ("is_data_relevant", "error_log")]

    for f in extract_fields:
        if f not in relevant.columns:
            print(f"  {f:<28} (column missing)")
            continue
        filled = relevant[f].notna().sum()
        flag = ""
        if filled == 0:
            flag = "  ⚠️  NULL 100%"
            null_100.append(f)
        print(f"  {f:<28} {bar(filled, total)}{flag}")

    if null_100:
        print(f"\n⚠️  Fields with 100% NULL (may need prompt fix):")
        for f in null_100:
            print(f"     • {f}")

    # Spot-check random relevant rows
    sample = relevant.sample(min(SPOT_CHECK_N, total), random_state=42)
    print(f"\n🔍 Spot-check {len(sample)} random relevant rows:\n")
    for idx, row in sample.iterrows():
        print(f"  ── idx={idx} | {row.get('title', '')} ──")
        for f in extract_fields:
            val = row.get(f)
            if pd.notna(val) and str(val).strip():
                preview = str(val)[:120].replace("\n", " ")
                print(f"    {f:<28}: {preview}")
        print()


# DATA SANITY
def check_sanity(df: pd.DataFrame):
    sep("5. DATA SANITY CHECKS")
    relevant = df[df["is_data_relevant"] == True]
    issues = False

    # 5a. Salary inversion
    if "min_salary_vnd" in df.columns and "max_salary_vnd" in df.columns:
        inv = relevant[
            relevant["min_salary_vnd"].notna() &
            relevant["max_salary_vnd"].notna() &
            (relevant["min_salary_vnd"] > relevant["max_salary_vnd"])
        ]
        if not inv.empty:
            print(f"⚠️  [Salary] {len(inv)} rows where min_salary > max_salary:")
            for idx, row in inv.head(5).iterrows():
                print(
                    f"    idx={idx}: min={row['min_salary_vnd']:,.0f}  "
                    f"max={row['max_salary_vnd']:,.0f}  | {row.get('title','')}"
                )
            issues = True
        else:
            print("✅ Salary range: no inversions.")

    # 5b. Experience inversion
    if "min_experience_years" in df.columns and "max_experience_years" in df.columns:
        inv = relevant[
            relevant["min_experience_years"].notna() &
            relevant["max_experience_years"].notna() &
            (relevant["min_experience_years"] > relevant["max_experience_years"])
        ]
        if not inv.empty:
            print(f"⚠️  [Experience] {len(inv)} rows where min_exp > max_exp:")
            for idx, row in inv.head(5).iterrows():
                print(
                    f"    idx={idx}: min={row['min_experience_years']}  "
                    f"max={row['max_experience_years']}  | {row.get('title','')}"
                )
            issues = True
        else:
            print("✅ Experience range: no inversions.")

    # 5c. Boolean field anomalies — values that are not True / False / None
    print("\n  Boolean field check:")
    for col in BOOLEAN_FIELDS:
        if col not in df.columns:
            continue
        bad = df[col].apply(lambda v: v not in (True, False, None))
        if bad.any():
            print(f"  ⚠️  '{col}': {bad.sum()} rows with unexpected values")
            print(f"       Sample: {df.loc[bad, col].head(3).tolist()}")
            issues = True
        else:
            print(f"  ✅ {col}")

    # 5d. extracted_skills — flag if more than 50% of relevant rows have empty skills
    if "extracted_skills" in relevant.columns:
        def _is_empty_skills(v):
            if pd.isna(v):
                return True
            try:
                parsed = json.loads(str(v))
                return isinstance(parsed, list) and len(parsed) == 0
            except Exception:
                return str(v).strip() in ("", "[]", "null")

        empty_skills = relevant[relevant["extracted_skills"].apply(_is_empty_skills)]
        pct = len(empty_skills) / len(relevant) * 100 if len(relevant) else 0
        if pct > 50:
            print(
                f"\n⚠️  extracted_skills empty in {len(empty_skills)}/{len(relevant)} "
                f"({pct:.1f}%) relevant rows — prompt may need adjustment."
            )
            issues = True
        else:
            print(
                f"\n✅ extracted_skills: "
                f"{len(relevant) - len(empty_skills)}/{len(relevant)} rows have skills."
            )

    # 5e. Error log summary
    if "error_log" in df.columns:
        errors = df["error_log"].notna().sum()
        if errors:
            print(f"\n⚠️  error_log: {errors} row(s) with errors — re-run to retry.")
            print("  Sample errors:")
            for val in df["error_log"].dropna().head(3):
                print(f"    {str(val)[:120]}")
            issues = True
        else:
            print("\n✅ error_log: no errors.")

    if not issues:
        print("\n✅ All sanity checks passed.")


# MAIN
def main():
    start_time = datetime.now()

    df = load_csv(INPUT_CSV)          # Step 1 — load + clean headers
    df = run_verification(df)         # Step 2 — Gemini verify + re-extract
    check_relevance(df)               # Step 3 — relevance distribution
    check_extraction_quality(df)      # Step 4 — fill-rate report
    check_sanity(df)                  # Step 5 — data sanity checks

    sep()
    elapsed = datetime.now() - start_time
    print(f"✅ Validation complete. Total time: {elapsed}\n")


if __name__ == "__main__":
    main()