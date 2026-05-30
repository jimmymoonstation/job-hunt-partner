"""
Seed the tracked_companies table with all known companies.
Safe to re-run — skips duplicates.
"""
import sys
sys.path.insert(0, "/opt/job-hunt-partner")

from src.api.database import SessionLocal
from src.api.models import TrackedCompany

SEED = [
    # ── Greenhouse ────────────────────────────────────────────────────────────
    *[{"company_name": n, "ats_type": "greenhouse", "ats_slug": s,
       "career_url": u} for n, s, u in [
        ("Stripe",        "stripe",       "https://stripe.com/jobs"),
        ("Databricks",    "databricks",   "https://www.databricks.com/company/careers"),
        ("Datadog",       "datadog",       "https://www.datadoghq.com/careers/"),
        ("Confluent",     "confluent",     "https://www.confluent.io/careers/"),
        ("HashiCorp",     "hashicorp",     "https://www.hashicorp.com/jobs"),
        ("Cloudflare",    "cloudflare",    "https://www.cloudflare.com/careers/"),
        ("Twilio",        "twilio",        "https://www.twilio.com/en-us/company/jobs"),
        ("SendGrid",      "sendgrid",      "https://www.twilio.com/en-us/company/jobs"),
        ("PagerDuty",     "pagerduty",     "https://www.pagerduty.com/careers/"),
        ("New Relic",     "newrelic",      "https://newrelic.com/about/careers"),
        ("GitHub",        "github",        "https://github.com/about/careers"),
        ("Airbnb",        "airbnb",        "https://careers.airbnb.com/"),
        ("Box",           "box",           "https://www.box.com/en-us/careers"),
        ("Lyft",          "lyft",          "https://www.lyft.com/careers"),
        ("DoorDash",      "doordash",      "https://careers.doordash.com/"),
        ("Coinbase",      "coinbase",      "https://www.coinbase.com/careers"),
        ("Reddit",        "reddit",        "https://www.redditinc.com/careers"),
        ("Pinterest",     "pinterest",     "https://www.pinterestcareers.com/"),
        ("Robinhood",     "robinhood",     "https://careers.robinhood.com/"),
        ("Plaid",         "plaid",         "https://plaid.com/careers/"),
        ("Chime",         "chime",         "https://careers.chime.com/"),
        ("Affirm",        "affirm",        "https://www.affirm.com/company/careers"),
        ("Carta",         "carta",         "https://carta.com/careers/"),
        ("Brex",          "brex",          "https://www.brex.com/careers"),
        ("Ramp",          "ramp",          "https://ramp.com/careers"),
        ("Anthropic",     "anthropic",     "https://www.anthropic.com/careers"),
        ("Cohere",        "cohere",        "https://cohere.com/careers"),
        ("Scale AI",      "scale",         "https://scale.com/careers"),
        ("Mistral AI",    "mistral",       "https://mistral.ai/careers"),
        ("Notion",        "notion",        "https://www.notion.so/careers"),
        ("Figma",         "figma",         "https://www.figma.com/careers/"),
        ("Airtable",      "airtable",      "https://airtable.com/careers"),
        ("Asana",         "asana",         "https://asana.com/jobs"),
        ("Dropbox",       "dropbox",       "https://www.dropbox.com/jobs"),
        ("Canva",         "canva",         "https://www.canva.com/careers/"),
        ("OpenAI",        "openai",        "https://openai.com/careers"),
        ("Waymo",         "waymo",         "https://waymo.com/careers/"),
        ("Zendesk",       "zendesk",       "https://www.zendesk.com/company/careers/"),
        ("Instacart",     "instacart",     "https://instacart.careers/"),
        ("Zscaler",       "zscaler",       "https://www.zscaler.com/careers"),
        ("Uber",          "uber",          "https://www.uber.com/us/en/careers/"),
        ("Unity",         "unity3d",       "https://careers.unity.com/"),
        ("Loom",          "loom",          "https://www.loom.com/careers"),
        ("Retool",        "retool",        "https://retool.com/careers"),
        # From curated spreadsheet
        ("CoreWeave",     "coreweave",     "https://coreweave.com/careers"),
        ("Twitch",        "twitch",        "https://www.twitch.tv/jobs"),
        ("New York Times","thenewyorktimes","https://www.nytco.com/careers/"),
        ("Dataiku",       "dataiku",       "https://www.dataiku.com/company/careers/"),
        ("Labelbox",      "labelbox",      "https://labelbox.com/careers/"),
        ("Thumbtack",     "thumbtack",     "https://www.thumbtack.com/careers/"),
        ("Upgrade",       "upgrade",       "https://www.upgrade.com/careers/"),
        ("Whatnot",       "whatnot",       "https://www.whatnot.com/careers"),
        ("Canonical",     "canonicaljobs", "https://canonical.com/careers"),
        ("Axon",          "axon",          "https://www.axon.com/careers"),
        ("KnowBe4",       "knowbe4",       "https://www.knowbe4.com/careers"),
        ("Recorded Future","recordedfuture","https://www.recordedfuture.com/careers"),
        ("Point72",       "point72",       "https://www.point72.com/careers/"),
        ("Insurify",      "insurify",      "https://insurify.com/careers/"),
        ("Sprout Social", "sproutsocialcollege", "https://sproutsocial.com/careers/"),
        ("Hudson River Trading", "wehrtyou", "https://www.hudsonrivertrading.com/careers/"),
        ("Figment",       "figment",       "https://figment.io/careers/"),
        ("Garner Health", "garnerhealth",  "https://www.garnerhealth.com/careers"),
        ("Pomelo Care",   "pomelocare",    "https://www.pomelocare.com/careers"),
        ("DeepMind",      "deepmind",      "https://deepmind.google/careers/"),
    ]],

    # ── Lever ─────────────────────────────────────────────────────────────────
    *[{"company_name": n, "ats_type": "lever", "ats_slug": s,
       "career_url": u} for n, s, u in [
        ("Netflix",      "netflix",    "https://jobs.netflix.com/"),
        ("Shopify",      "shopify",    "https://www.shopify.com/careers"),
        ("Netlify",      "netlify",    "https://www.netlify.com/careers/"),
        ("Vercel",       "vercel",     "https://vercel.com/careers"),
        ("Supabase",     "supabase",   "https://supabase.com/careers"),
        ("Linear",       "linear",     "https://linear.app/careers"),
        ("Descript",     "descript",   "https://www.descript.com/careers"),
        ("Segment",      "segment",    "https://www.twilio.com/en-us/company/jobs"),
        ("Mixpanel",     "mixpanel",   "https://mixpanel.com/jobs/"),
        ("Amplitude",    "amplitude",  "https://amplitude.com/careers"),
        ("Heap",         "heap",       "https://heap.io/careers"),
        ("Benchling",    "benchling",  "https://www.benchling.com/careers"),
        ("Palantir",     "palantir",   "https://www.palantir.com/careers/"),
        ("Grammarly",    "grammarly",  "https://www.grammarly.com/jobs"),
        ("Flexport",     "flexport",   "https://www.flexport.com/careers/"),
        # From curated spreadsheet
        ("Spotify",      "spotify",    "https://www.lifeatspotify.com/jobs"),
        ("Veeva",        "veeva",      "https://careers.veeva.com/"),
        ("StackAdapt",   "stackadapt", "https://www.stackadapt.com/careers"),
        ("Match Group",  "matchgroup", "https://mtch.com/careers"),
        ("Whoop",        "whoop",      "https://www.whoop.com/careers/"),
        ("Dun & Bradstreet", "dnb",    "https://www.dnb.com/about-us/careers.html"),
        ("Waabi",        "waabi",      "https://waabi.ai/careers/"),
        ("Hive",         "hive",       "https://thehive.ai/careers"),
        ("MeridianLink", "meridianlink","https://meridianlink.com/careers/"),
        ("Houzz",        "houzz",      "https://www.houzz.com/careers"),
        ("Alloy.ai",     "alloy",      "https://alloy.ai/careers/"),
        ("Kumo",         "kumo",       "https://kumo.ai/careers/"),
    ]],

    # ── Ashby ─────────────────────────────────────────────────────────────────
    *[{"company_name": n, "ats_type": "ashby", "ats_slug": s,
       "career_url": u} for n, s, u in [
        ("Perplexity",       "perplexity",        "https://www.perplexity.ai/careers"),
        ("Anduril",          "anduril",           "https://www.anduril.com/careers/"),
        ("Mercury",          "mercury",           "https://mercury.com/jobs"),
        ("Rippling",         "rippling",          "https://www.rippling.com/careers"),
        ("Deel",             "deel",              "https://www.deel.com/careers"),
        ("Watershed",        "watershed",         "https://watershed.com/careers"),
        ("Airbyte",          "airbyte",           "https://airbyte.com/careers"),
        ("Fivetran",         "fivetran",          "https://www.fivetran.com/careers"),
        ("Hightouch",        "hightouch",         "https://hightouch.com/careers"),
        ("dbt Labs",         "dbt-labs",          "https://www.getdbt.com/dbt-labs/open-roles/"),
        ("Metabase",         "metabase",          "https://www.metabase.com/jobs"),
        ("Census",           "census",            "https://www.getcensus.com/careers"),
        ("Modern Treasury",  "modern-treasury",   "https://www.moderntreasury.com/careers"),
        ("Gusto",            "gusto",             "https://gusto.com/about/careers"),
        ("Lattice",          "lattice",           "https://lattice.com/careers"),
        ("Coda",             "coda",              "https://coda.io/careers"),
        # From curated spreadsheet
        ("Statsig",          "statsig",           "https://www.statsig.com/careers"),
        ("Imprint",          "imprint",           "https://www.imprint.co/careers"),
        ("Kikoff",           "kikoff",            "https://kikoff.com/careers"),
        ("Zefr",             "zefr",              "https://www.zefr.com/careers"),
        ("HaydenAI",         "haydenai",          "https://www.hayden.ai/careers"),
    ]],

    # ── Workday ───────────────────────────────────────────────────────────────
    *[{"company_name": n, "ats_type": "workday", "ats_slug": s,
       "workday_wd_ver": v, "workday_board": b, "career_url": u} for n, s, v, b, u in [
        ("Salesforce",   "salesforce",  "wd12", "External_Career_Site",      "https://salesforce.com/company/careers/"),
        ("NVIDIA",       "nvidia",      "wd5",  "NVIDIAExternalCareerSite",   "https://www.nvidia.com/en-us/about-nvidia/careers/"),
        ("Adobe",        "adobe",       "wd5",  "external_experienced",       "https://www.adobe.com/careers.html"),
        ("Zoom",         "zoom",        "wd5",  "Zoom",                       "https://careers.zoom.us/"),
        ("Workday",      "workday",     "wd5",  "workday",                    "https://www.workday.com/en-us/company/careers.html"),
        ("Cisco",        "cisco",       "wd5",  "Cisco_Careers",              "https://jobs.cisco.com/"),
        ("Intel",        "intel",       "wd1",  "External",                   "https://jobs.intel.com/"),
        ("HPE",          "hpe",         "wd5",  "Jobsathpe",                  "https://careers.hpe.com/"),
        ("Broadcom",     "broadcom",    "wd1",  "External_Career",            "https://careers.broadcom.com/"),
        ("Snap",         "snapchat",    "wd1",  "snap",                       "https://careers.snap.com/"),
        # From curated spreadsheet — boards confirmed from real job URLs
        ("Disney",       "disney",      "wd5",  "disneycareer",               "https://jobs.disneycareers.com/"),
        ("CrowdStrike",  "crowdstrike", "wd5",  "crowdstrikecareers",         "https://www.crowdstrike.com/en-us/careers/"),
        ("Nike",         "nike",        "wd1",  "nke",                        "https://jobs.nike.com/"),
        ("Walmart",      "walmart",     "wd5",  "WalmartExternal",            "https://careers.walmart.com/"),
        ("Target",       "target",      "wd5",  "targetcareers",              "https://jobs.target.com/"),
        ("Gartner",      "gartner",     "wd5",  "EXT",                        "https://jobs.gartner.com/"),
        ("Morgan Stanley","ms",         "wd5",  "External",                   "https://www.morganstanley.com/people-opportunities"),
        ("TransUnion",   "transunion",  "wd5",  "TransUnion",                 "https://careers.transunion.com/"),
        ("Amgen",        "amgen",       "wd1",  "Careers",                    "https://careers.amgen.com/"),
        ("GSK",          "gsk",         "wd5",  "gskcareers",                 "https://jobs.gsk.com/"),
        ("Dexcom",       "dexcom",      "wd1",  "dexcom",                     "https://careers.dexcom.com/"),
        ("Moderna",      "modernatx",   "wd1",  "M_tx",                       "https://www.modernatx.com/careers"),
        ("Merck",        "msd",         "wd5",  "SearchJobs",                 "https://jobs.merck.com/"),
        ("S&P Global",   "spgi",        "wd5",  "SPGI_Careers",               "https://careers.spglobal.com/"),
        ("Booz Allen",   "bah",         "wd1",  "BAH_Jobs",                   "https://careers.boozallen.com/"),
        ("Verily",       "verily",      "wd1",  "verily",                     "https://verily.com/careers/"),
        ("Applied Materials","amat",    "wd1",  "External",                   "https://www.appliedmaterials.com/us/en/careers.html"),
        ("Sanofi",       "sanofi",      "wd3",  "SanofiCareers",              "https://www.sanofi.com/en/careers"),
        ("Cadence",      "cadence",     "wd1",  "External_Careers",           "https://cadence.wd1.myworkdayjobs.com/External_Careers"),
    ]],

    # ── SmartRecruiters ───────────────────────────────────────────────────────
    *[{"company_name": n, "ats_type": "smartrecruiters", "ats_slug": s,
       "career_url": u} for n, s, u in [
        ("ServiceNow",        "servicenow",         "https://careers.servicenow.com/"),
        ("Palo Alto Networks","paloaltonetworks2",   "https://jobs.paloaltonetworks.com/"),
        ("Block",             "Square",              "https://careers.block.xyz/"),
    ]],

    # ── Amazon (custom scraper) ───────────────────────────────────────────────
    {"company_name": "Amazon", "ats_type": "amazon", "ats_slug": "amazon",
     "career_url": "https://amazon.jobs/"},

    # ── Custom / blocked — career URL stored for reference ───────────────────
    *[{"company_name": n, "ats_type": "custom", "ats_slug": s,
       "career_url": u} for n, s, u in [
        ("Google",       "careers.google.com",     "https://careers.google.com/"),
        ("Meta",         "metacareers.com",         "https://www.metacareers.com/"),
        ("Microsoft",    "careers.microsoft.com",   "https://careers.microsoft.com/"),
        ("Apple",        "jobs.apple.com",          "https://jobs.apple.com/"),
        ("Tesla",        "tesla.com",               "https://www.tesla.com/careers"),
        ("TikTok",       "careers.tiktok.com",      "https://lifeattiktok.com/"),
        ("ByteDance",    "jobs.bytedance.com",       "https://jobs.bytedance.com/"),
        ("Twitter/X",    "careers.x.com",           "https://careers.x.com/"),
        ("Spotify",      "lifeatspotify.com",        "https://lifeatspotify.com/jobs"),
        ("Qualcomm",     "qualcomm.wd5.myworkdayjobs.com", "https://careers.qualcomm.com/"),
        ("Oracle",       "careers.oracle.com",      "https://careers.oracle.com/"),
        ("IBM",          "ibm.com",                 "https://www.ibm.com/careers"),
        ("Snowflake",    "careers.snowflake.com",   "https://careers.snowflake.com/"),
        ("Splunk",       "splunk.com",              "https://www.splunk.com/en_us/careers.html"),
        ("Intuit",       "jobs.intuit.com",         "https://jobs.intuit.com/"),
        ("Okta",         "okta.com",                "https://www.okta.com/company/careers/"),
        ("Lyft",         "lyft.com",                "https://www.lyft.com/careers"),
        ("VMware",       "careers.vmware.com",      "https://careers.vmware.com/"),
        ("Fortinet",     "fortinet.com",            "https://www.fortinet.com/corporate/careers"),
    ]],
]


def seed():
    with SessionLocal() as db:
        inserted = 0
        skipped = 0
        for entry in SEED:
            existing = db.query(TrackedCompany).filter_by(
                ats_type=entry["ats_type"], ats_slug=entry["ats_slug"]
            ).first()
            if existing:
                # Update career_url and workday fields if missing
                changed = False
                if not existing.career_url and entry.get("career_url"):
                    existing.career_url = entry["career_url"]
                    changed = True
                if entry.get("workday_wd_ver") and not existing.workday_wd_ver:
                    existing.workday_wd_ver = entry["workday_wd_ver"]
                    changed = True
                if entry.get("workday_board") and not existing.workday_board:
                    existing.workday_board = entry["workday_board"]
                    changed = True
                if changed:
                    db.add(existing)
                skipped += 1
                continue
            company = TrackedCompany(
                company_name=entry["company_name"],
                ats_type=entry["ats_type"],
                ats_slug=entry["ats_slug"],
                workday_board=entry.get("workday_board"),
                workday_wd_ver=entry.get("workday_wd_ver", "wd5"),
                career_url=entry.get("career_url"),
                discovered_from="seed",
            )
            db.add(company)
            inserted += 1
        db.commit()
        print(f"Seeded {inserted} companies, skipped {skipped} duplicates")


if __name__ == "__main__":
    seed()
