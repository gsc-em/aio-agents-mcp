"""
Parse EU + LatAm grocery banner attribution xlsx files into clean normalized CSVs.

Output:
  - banners.csv          (one row per banner, with all attributes)
  - markets.csv          (one row per market with summary stats)
  - erp_systems.csv      (lookup of distinct ERP systems)
  - procurement_platforms.csv
  - clouds.csv
  - confidence_tiers.csv
"""
import pandas as pd
import re
from pathlib import Path

EU_FILE = '/mnt/user-data/uploads/EU__Grocery_and_Hyperscaler_Market.xlsx'
LATAM_FILE = '/mnt/user-data/uploads/LatAm_Grocery_and_Hyperscaler_Market.xlsx'
OUT_DIR = Path('/home/claude/aio-agents-mcp/data')

# Sheet name -> ISO country code mapping for EU file
EU_SHEET_TO_COUNTRY = {
    'DE': ('DE', 'Germany', 'Western EU + DACH'),
    'FR': ('FR', 'France', 'Western EU'),
    'UK': ('GB', 'United Kingdom', 'Western EU + UK + IE'),
    'IE': ('IE', 'Ireland', 'Western EU + UK + IE'),
    'IT': ('IT', 'Italy', 'Iberia + Italy'),
    'ES': ('ES', 'Spain', 'Iberia + Italy'),
    'PT': ('PT', 'Portugal', 'Iberia + Italy'),
    'NL': ('NL', 'Netherlands', 'Benelux'),
    'BE': ('BE', 'Belgium', 'Benelux'),
    'LU': ('LU', 'Luxembourg', 'Benelux'),
    'AT': ('AT', 'Austria', 'DACH'),
    'CH': ('CH', 'Switzerland', 'DACH'),
    'NO': ('NO', 'Norway', 'Nordics'),
    'SE': ('SE', 'Sweden', 'Nordics'),
    'DK': ('DK', 'Denmark', 'Nordics'),
    'FI': ('FI', 'Finland', 'Nordics'),
    'PL': ('PL', 'Poland', 'CEE'),
    'CZ': ('CZ', 'Czech Republic', 'CEE'),
}

LATAM_SHEET_TO_COUNTRY = {
    'BRASIL': ('BR', 'Brazil', 'LatAm'),
    'MEXICO ': ('MX', 'Mexico', 'LatAm'),
    'COLOMBIA': ('CO', 'Colombia', 'LatAm'),
    'CHILE': ('CL', 'Chile', 'LatAm'),
    'ARGENTINA': ('AR', 'Argentina', 'LatAm'),
    'PERU': ('PE', 'Peru', 'LatAm'),
    'ECUADOR': ('EC', 'Ecuador', 'LatAm'),
    'CR+': ('CR', 'Costa Rica + Central America', 'LatAm'),
    'DR': ('DO', 'Dominican Republic', 'LatAm'),
    'PR-Carib': ('PR', 'Puerto Rico + Caribbean', 'LatAm'),
}


def strip_emoji_prefix(s):
    """Remove leading emoji + whitespace from cell values like '🟢 SAP S/4HANA'."""
    if not s:
        return s
    # Strip common confidence/status emojis from the start
    return re.sub(r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\s]+', '', str(s)).strip()


def normalize_confidence(raw):
    """Map raw confidence text to standard tier."""
    if not raw or pd.isna(raw):
        return 'UNKNOWN'
    s = str(raw).upper()
    if 'CONFIRMED' in s:
        return 'CONFIRMED'
    if 'PROBABLE' in s:
        return 'PROBABLE'
    if 'INFERRED' in s:
        return 'INFERRED'
    if 'CONTESTED' in s:
        return 'CONTESTED'
    return 'UNKNOWN'


def normalize_cloud(raw):
    """Extract primary cloud designation."""
    if not raw or pd.isna(raw):
        return None
    s = strip_emoji_prefix(raw)
    # Order matters - check most specific first
    clouds = []
    for cloud in ['STACKIT', 'OCI', 'HEC', 'Azure', 'GCP', 'AWS', 'On-prem', 'Hybrid', 'Private Cloud']:
        if cloud.lower() in s.lower():
            clouds.append(cloud)
    if not clouds:
        if 'unknown' in s.lower():
            return 'Unknown'
        return s.strip()[:60]
    return ', '.join(clouds)


def normalize_erp(raw):
    """Extract primary ERP system."""
    if not raw or pd.isna(raw):
        return None
    s = strip_emoji_prefix(raw)
    erps = []
    for erp in ['SAP S/4HANA', 'SAP ECC', 'Oracle Fusion', 'Oracle Cloud', 'Oracle Retail',
                'D365', 'Dynamics AX', 'Infor CloudSuite', 'Infor', 'Totvs Protheus', 'Totvs',
                'CSB-System', 'Mainframe', 'Custom']:
        if erp.lower() in s.lower():
            erps.append(erp)
            break  # take first match (most specific)
    if not erps:
        if 'unknown' in s.lower():
            return 'Unknown'
        return s.strip()[:80]
    return erps[0]


def normalize_procurement(raw):
    """Extract procurement platform."""
    if not raw or pd.isna(raw):
        return None
    s = strip_emoji_prefix(raw)
    platforms = []
    for plat in ['Ariba', 'Coupa', 'Ivalua', 'GEP SMART', 'GEP', 'JAGGAER', 'Zycus',
                 'Determine', 'Oracle Procurement', 'SAP CAR', 'SAP PMR', 'Native', 'Manual', 'EDI']:
        if plat.lower() in s.lower():
            platforms.append(plat)
    if not platforms:
        if 'unknown' in s.lower():
            return 'Unknown'
        return s.strip()[:80]
    return ', '.join(platforms[:3])


def parse_country_sheet(filepath, sheet_name, country_iso, country_name, region):
    """Extract banner attribution rows from one country sheet."""
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    rows = []

    # The structured attribution table is in columns 3-7 (or similar)
    # Header row contains: Banner | ERP | Cloud | Procurement | Confidence
    # LatAm variant: # | Banner | ERP System | Procurement | Hyperscaler | Confidence
    # We need to find the header row first
    header_row = None
    for i, row in df.iterrows():
        cells = [str(c).strip().lower() if pd.notna(c) else '' for c in row]
        has_banner = 'banner' in cells
        has_erp = any('erp' in c for c in cells)
        has_cloud = 'cloud' in cells or 'hyperscaler' in cells
        if has_banner and has_erp and has_cloud:
            header_row = i
            # Find which columns hold each field
            col_map = {}
            for j, cell in enumerate(cells):
                if cell == 'banner':
                    col_map['banner'] = j
                elif 'erp' in cell:
                    col_map['erp'] = j
                elif cell == 'cloud' or cell == 'hyperscaler':
                    col_map['cloud'] = j
                elif 'procurement' in cell:
                    col_map['procurement'] = j
                elif 'confidence' in cell:
                    col_map['confidence'] = j
            break

    if header_row is None:
        # No structured table found - fall back to column 0 banner list only
        for i, row in df.iterrows():
            val = row.iloc[0] if len(row) > 0 else None
            if pd.notna(val) and str(val).strip() and not str(val).startswith('🇩🇪') \
               and not str(val).startswith('🇫🇷') and '—' not in str(val) and len(str(val)) < 80:
                rows.append({
                    'banner': str(val).strip(),
                    'country_iso': country_iso,
                    'country_name': country_name,
                    'region': region,
                    'erp': None, 'cloud': None, 'procurement': None,
                    'confidence': 'UNKNOWN', 'raw_notes': None
                })
        return rows

    # Extract structured rows after header
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i]
        banner = row.iloc[col_map['banner']] if 'banner' in col_map else None
        if pd.isna(banner) or not str(banner).strip():
            continue
        banner_str = str(banner).strip()
        # Skip section headers / emoji rows
        if banner_str.startswith('🇩') or banner_str.startswith('🇫') or banner_str.startswith('🎯'):
            continue
        if len(banner_str) > 200:  # likely a paragraph, not a banner name
            continue

        erp = row.iloc[col_map['erp']] if 'erp' in col_map else None
        cloud = row.iloc[col_map['cloud']] if 'cloud' in col_map else None
        procurement = row.iloc[col_map['procurement']] if 'procurement' in col_map else None
        confidence = row.iloc[col_map['confidence']] if 'confidence' in col_map else None

        rows.append({
            'banner': banner_str[:120],
            'country_iso': country_iso,
            'country_name': country_name,
            'region': region,
            'erp': normalize_erp(erp),
            'cloud': normalize_cloud(cloud),
            'procurement': normalize_procurement(procurement),
            'confidence': normalize_confidence(confidence),
            'raw_notes': str(confidence) if pd.notna(confidence) else None,
        })
    return rows


def main():
    all_rows = []

    print("Parsing EU file...")
    eu_xl = pd.ExcelFile(EU_FILE)
    for sheet, (iso, name, region) in EU_SHEET_TO_COUNTRY.items():
        if sheet in eu_xl.sheet_names:
            sheet_rows = parse_country_sheet(EU_FILE, sheet, iso, name, region)
            print(f"  {sheet:6} ({iso}) → {len(sheet_rows)} banners")
            all_rows.extend(sheet_rows)

    print("\nParsing LatAm file...")
    latam_xl = pd.ExcelFile(LATAM_FILE)
    for sheet, (iso, name, region) in LATAM_SHEET_TO_COUNTRY.items():
        if sheet in latam_xl.sheet_names:
            sheet_rows = parse_country_sheet(LATAM_FILE, sheet, iso, name, region)
            print(f"  {sheet:12} ({iso}) → {len(sheet_rows)} banners")
            all_rows.extend(sheet_rows)

    # Build banners DataFrame
    banners = pd.DataFrame(all_rows)
    banners.insert(0, 'banner_id', range(1, len(banners) + 1))
    banners.to_csv(OUT_DIR / 'banners.csv', index=False)
    print(f"\n✓ Wrote banners.csv: {len(banners)} rows")

    # Build markets summary
    markets = banners.groupby(['country_iso', 'country_name', 'region']).agg(
        banner_count=('banner', 'count'),
        confirmed=('confidence', lambda x: (x == 'CONFIRMED').sum()),
        probable=('confidence', lambda x: (x == 'PROBABLE').sum()),
        inferred=('confidence', lambda x: (x == 'INFERRED').sum()),
        unknown=('confidence', lambda x: (x == 'UNKNOWN').sum()),
    ).reset_index()
    markets.insert(0, 'market_id', range(1, len(markets) + 1))
    markets.to_csv(OUT_DIR / 'markets.csv', index=False)
    print(f"✓ Wrote markets.csv: {len(markets)} rows")

    # Lookup tables
    erp_lookup = pd.DataFrame({
        'erp_id': range(1, banners['erp'].dropna().nunique() + 1),
        'erp_name': sorted(banners['erp'].dropna().unique())
    })
    erp_lookup.to_csv(OUT_DIR / 'erp_systems.csv', index=False)
    print(f"✓ Wrote erp_systems.csv: {len(erp_lookup)} rows")

    proc_lookup = pd.DataFrame({
        'procurement_id': range(1, banners['procurement'].dropna().nunique() + 1),
        'procurement_name': sorted(banners['procurement'].dropna().unique())
    })
    proc_lookup.to_csv(OUT_DIR / 'procurement_platforms.csv', index=False)
    print(f"✓ Wrote procurement_platforms.csv: {len(proc_lookup)} rows")

    cloud_lookup = pd.DataFrame({
        'cloud_id': range(1, banners['cloud'].dropna().nunique() + 1),
        'cloud_name': sorted(banners['cloud'].dropna().unique())
    })
    cloud_lookup.to_csv(OUT_DIR / 'clouds.csv', index=False)
    print(f"✓ Wrote clouds.csv: {len(cloud_lookup)} rows")

    confidence_lookup = pd.DataFrame({
        'confidence_id': [1, 2, 3, 4, 5],
        'tier': ['CONFIRMED', 'PROBABLE', 'INFERRED', 'CONTESTED', 'UNKNOWN'],
        'description': [
            'Cross-LLM consensus (5-of-6 or 6-of-6)',
            'Likely accurate, partial LLM agreement',
            'Inferred from parent group / corporate structure',
            'Sources disagree, manual review needed',
            'No reliable attribution available',
        ]
    })
    confidence_lookup.to_csv(OUT_DIR / 'confidence_tiers.csv', index=False)
    print(f"✓ Wrote confidence_tiers.csv: 5 rows")

    # Print summary stats
    print(f"\n=== ATTRIBUTION SUMMARY ===")
    print(f"Total banners       : {len(banners)}")
    print(f"  CONFIRMED         : {(banners['confidence'] == 'CONFIRMED').sum()}")
    print(f"  PROBABLE          : {(banners['confidence'] == 'PROBABLE').sum()}")
    print(f"  INFERRED          : {(banners['confidence'] == 'INFERRED').sum()}")
    print(f"  CONTESTED         : {(banners['confidence'] == 'CONTESTED').sum()}")
    print(f"  UNKNOWN           : {(banners['confidence'] == 'UNKNOWN').sum()}")
    print(f"Banners with ERP    : {banners['erp'].notna().sum()}")
    print(f"Banners with cloud  : {banners['cloud'].notna().sum()}")
    print(f"Banners with proc.  : {banners['procurement'].notna().sum()}")
    print(f"Distinct ERPs       : {banners['erp'].nunique()}")
    print(f"Distinct clouds     : {banners['cloud'].nunique()}")
    print(f"Distinct procurement: {banners['procurement'].nunique()}")
    print(f"Markets covered     : {banners['country_iso'].nunique()}")


if __name__ == '__main__':
    main()
