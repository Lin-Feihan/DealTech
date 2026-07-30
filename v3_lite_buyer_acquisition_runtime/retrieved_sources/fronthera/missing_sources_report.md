# M2 Real-Source Partial Coverage Report

Case: FronThera / Esker / Alumis
Runtime scope: V3-Lite M2 manual_retrieved_sources
Status: PARTIAL COVERAGE - raw evidence may be extracted only from retrieved authoritative sources

## Decision

Create a partial `retrieved_sources_manifest.json` for available authoritative sources and record unavailable source categories in `failed_source_needs`.

M2 should fail closed only when there are zero valid authoritative retrieved sources or when the manifest itself is invalid. An incomplete but valid authoritative source set may proceed through M2 raw-evidence extraction with `evidence_coverage_status: partial`.

M2 must not enter M3. This run must not generate `evidence_repository.json`, `claim_evidence_graph.json`, `certification_result.json`, or `final_report.md`.

## Created Location

- Directory: `v3_lite_buyer_acquisition_runtime/retrieved_sources/fronthera/`
- Manifest: `v3_lite_buyer_acquisition_runtime/retrieved_sources/fronthera/retrieved_sources_manifest.json`
- Cache directory: `v3_lite_buyer_acquisition_runtime/retrieved_sources/fronthera/cache/`

## Official Candidate Sources Retrieved

These files were downloaded directly from official source owners and are included in the partial manifest.

1. SEC Exhibit 10.22 / Stock Purchase Agreement
   - Official URL: `https://www.sec.gov/Archives/edgar/data/1847367/000110465924069735/tm2411163d6_ex10-22.htm`
   - Cached file: `cache/sec_exhibit_10_22_stock_purchase_agreement.htm`
   - Observed anchors: `STOCK PURCHASE AGREEMENT`, `March 5, 2021`, `FL2021-001`, `FronThera International Group Limited`, `FronThera U.S. Holdings, Inc.`, `$60,000,000`, `$120,000,000`, `TYK2 Portfolio`, `PCT/US2019/057485`, `PCT/US2020/021850`, `US16/938,183`, `US63/079,217`.

2. Alumis SEC 424B4 prospectus
   - Official URL: `https://www.sec.gov/Archives/edgar/data/1847367/000110465924076337/tm2411163-14_424b4.htm`
   - Cached file: `cache/sec_alumis_424b4_2024.htm`
   - Observed anchors: Alumis IPO prospectus, TYK2 franchise, ESK-001, clinical-stage pipeline context.

3. Alumis SEC 2025 10-K
   - Official URL: `https://www.sec.gov/Archives/edgar/data/1847367/000184736725000012/tmb-20241231x10k.htm`
   - Cached file: `cache/sec_alumis_2025_10k.htm`

4. Alumis SEC 2026 10-K
   - Official URL: `https://www.sec.gov/Archives/edgar/data/1847367/000184736726000006/alms-20251231x10k.htm`
   - Cached file: `cache/sec_alumis_2026_10k.htm`

5. Alumis official pipeline page
   - Official URL: `https://www.alumis.com/pipeline/`
   - Cached file: `cache/alumis_pipeline_page.html`
   - Observed anchors: `Envudeucitinib`, `TYK2`, plaque psoriasis, SLE, A-005.

## Failed Source Needs Still Missing

These missing categories are recorded in the manifest `failed_source_needs` and should remain gaps until supplied by a human or a future retrieval provider.

1. Haisco / CNINFO / SZSE disclosure showing Bohan Jin role and 2017 11.12% shareholding
   - Needed official source owner: Haisco Pharmaceutical Group Co., Ltd. / CNINFO / Shenzhen Stock Exchange disclosure platform.
   - Attempted official access:
     - CNINFO stock disclosure page for `002653` was reachable, but did not return a usable concrete announcement page through the tested URL.
     - CNINFO historical announcement API searches for `FronThera`, `Bohan Jin`, `11.12`, `TYK2`, `前沿`, `金博涵`, `博涵`, and `海思科 FronThera` returned no matching announcements in this environment.
   - Status: missing. Do not infer from case_seed, mandate notes, Bohan PDF, fixtures, or SEC agreement context.

2. Official patent-office records for TYK2 inhibitor chemistry
   - Needed official source owner: WIPO PATENTSCOPE, USPTO Patent Public Search / Patent Center, EPO Espacenet, or another official patent office database.
   - Lead identifiers observed in SEC Exhibit 10.22: `PCT/US2019/057485`, `PCT/US2020/021850`, `US16/938,183`, `US63/079,217`.
   - Attempted official access:
     - USPTO Patent Public Search landing page was reachable, but search result source text was not extractable.
     - WIPO PATENTSCOPE returned HTTP 403 for attempted query/detail access.
     - Google Patents timed out and is not the preferred official source owner.
   - Status: missing. SEC Exhibit 10.22 may provide patent leads, but is not an official patent-office record.

3. Direct source on Bohan Jin personal realized proceeds
   - Status: missing. Do not infer proceeds from ownership leads or transaction consideration.

4. Immediately pre-2021 FronThera cap table source
   - Status: missing. Leave cap table coverage as a gap.

## Runtime Controls

- `evidence_coverage_status`: `partial`
- `case_seed` must not be used as evidence.
- mandate notes must not be used as evidence.
- Bohan PDF must not be used.
- test fixtures must not be used in the real-source run.
- no live search should be faked by the runtime.
- no downstream M3 artifacts should be generated.
