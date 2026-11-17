# AUDIT-CRITERIA.md — Compliance Report Generator

> SAAF A2 standard (Audit Criteria & Controls). This document sits next to `README.md`: the README says what the agent does and how to run it; this document says what the agent must be judged against as an auditee.
>
> **Scope of this revision.** Every claim below describes the code and tests at commit `311496ae1e029523db91a2c763ce9477c626df11` (`311496a`, 2026-11-10), revised on 2026-11-10 after the review in issue #52. It does not describe later commits. It is a statement about that snapshot, not a standing description of `main`.
>
> **Sources.** `README.md`; the code (`cli.py`, `config.py`, `saaf/`) and tests (`tests/`) at that commit, read directly; the suite and local probes described in section 6; the primary framework sources named in section 2. Earlier drafts also drew on the hackathon plan (`plans/hackathon-2/rohan-sobha-compliance-report-generator.md` in SAAF-Project). No Session 6 A2 hand-in existed.
>
> **Evidence boundary.** No live-model execution evidence is included in this assessment. The automated suite uses mocks, stubs, local servers, and dry runs. Any historical Claude usage is outside the verified evidence set.
>
> **Branch note.** This document covers `main` at the commit above. Open PRs #50, #51, #53, #54 and #63 change behaviour or tests described here. None of them is merged at this commit, so none of their changes counts as evidence. PR #51 has since merged (`b114bb9`): `_parse_and_validate` now always overwrites `audit_input` with the trusted input and logs a warning when the model's value differs, covered by `TestAuditInputAgentOwned.*` and `TestEntityNameDataFlow.test_anonymised_run_ignores_model_audit_input_and_restores_real_name`. This assessment has not been re-run against that commit, so CO-5.10 below still reflects `311496a`.

---

## Metadata

| Field | Value |
|---|---|
| **Agent** | Compliance Report Generator |
| **Repository** | https://github.com/SAAF-Project/Compliance-Report-Generator |
| **Maintainer(s)** | Rohan Sobha |
| **Last reviewed** | 2026-11-10 |
| **Assessed commit** | `311496ae1e029523db91a2c763ce9477c626df11` |
| **Status** | Draft |

## 1. What the agent does

Given an engagement profile (company name, industry, country, listed status, audit topic), the agent deterministically maps the entity to applicable regulatory frameworks from a built-in knowledge base (30 frameworks, at most 8 selected per run), then asks an LLM (default Claude `claude-opus-4-6` with adaptive thinking; any OpenAI-compatible endpoint can be configured with `--provider` / `--model` / `--base-url`) to produce a structured compliance overview: mandatory regulations, per-framework control objectives with testing approaches, typical gaps, and a prioritised action summary. Clause references it cites are checked for existence against official clause lists where one is shipped. Output is validated against Pydantic models and rendered as a terminal report or JSON. It supports the **planning phase** of an audit engagement (regulatory scoping); it does not assess the entity's actual compliance.

AI-specific risks are relevant because the system uses an LLM. Articles 12–15 of the EU AI Act are used here as control-design benchmarks; their inclusion does not establish that the system is legally classified as high-risk. Legal applicability requires a separate assessment.

## 2. Control objectives & framework mapping

These describe the agent's own trustworthy behaviour, not the regulations it reports on.

| Control objective | Why relevant |
|---|---|
| **CO-1 — Framework scoping is grounded.** Framework and regulation names must resolve to the mapped framework set. For supported clause lists, the agent must record clause-existence check outcomes and flag references not found. These checks do not establish semantic correctness. Unsupported reference coverage must be explicitly disclosed. | The core risk of this agent is a plausible but invented regulation or clause reaching an audit plan. |
| **CO-2 — Output is structurally valid.** The agent may perform explicitly documented JSON extraction and application-owned field derivation. It must reject schema-invalid substantive model content rather than inventing missing substantive values or returning a partial report. | Auditors consume the JSON downstream; invalid output must fail loudly. |
| **CO-3 — Output is positioned as decision support.** A human-review disclaimer accompanies the report, and model-generated content is not presented as legal or audit-ready conclusions. | Output is generic to a profile and not tested against real entity evidence. |
| **CO-4 — Engagement data and secrets are handled deliberately.** The CLI takes the API key from the environment, no real entity data is needed to use the agent, and what leaves the machine is documented. | Company name and profile are sent to the configured model endpoint, which may be third-party or self-hosted. |
| **CO-5 — Runs are attributable and sufficiently documented for review; exact output reproducibility is not guaranteed.** | A reviewer must be able to see what produced a report. |

Mapping basis values: *legal applicability pending* means the instrument is used as a design benchmark and whether it binds this system has not been assessed; *voluntary benchmark* means a non-binding control or risk catalogue; *professional-practice reference* means a standard for the auditors who use the output, not a requirement on the software.

| CO | Reference | Edition | Mapping basis | Source check (2026-11-10) |
|---|---|---|---|---|
| CO-1 | OWASP LLM09:2025 Misinformation (constrained output scope). The 2025 page treats overreliance as a related issue. | OWASP Top 10 for LLM Applications 2025 | Voluntary benchmark | Identifier and title confirmed on genai.owasp.org |
| CO-1 | OWASP LLM01:2025 Prompt Injection | OWASP Top 10 for LLM Applications 2025 | Voluntary benchmark | Identifier and title confirmed on genai.owasp.org |
| CO-1 | EU AI Act Art. 15, accuracy, robustness and cybersecurity | Regulation (EU) 2024/1689 | Legal applicability pending | Title confirmed on the Commission's AI Act Service Desk |
| CO-2 | EU AI Act Art. 15 | Regulation (EU) 2024/1689 | Legal applicability pending | As above |
| CO-2 | COBIT DSS06, business process controls | COBIT 2019 | Voluntary benchmark | Not re-checked against the primary text in this revision |
| CO-3 | EU AI Act Art. 14, human oversight | Regulation (EU) 2024/1689 | Legal applicability pending | Title confirmed on artificialintelligenceact.eu |
| CO-3 | EU AI Act Art. 13, transparency and provision of information to deployers | Regulation (EU) 2024/1689 | Legal applicability pending | Title confirmed on artificialintelligenceact.eu |
| CO-3 | IIA Standard 4.2, Due Professional Care (legacy 1220) | Global Internal Audit Standards, published 2024-01-09, effective 2025-01-09 | Professional-practice reference | Number, title and legacy mapping confirmed in the IIA standards and standards-mapping PDFs; effective date from the IIA press release |
| CO-3 | IIA Standard 14.1, Gathering Information for Analyses and Evaluation (legacy 2310) | Global Internal Audit Standards | Professional-practice reference | As above |
| CO-4 | GDPR Art. 5(1)(c) data minimisation; Art. 32 security of processing | Regulation (EU) 2016/679 | Legal applicability pending: depends on the deployment and on whether submitted values are personal data | Not re-checked against the primary text in this revision |
| CO-4 | ISO/IEC 27001 Annex A 5.17, 8.24 | ISO/IEC 27001:2022 | Voluntary benchmark | Not re-checked against the primary text in this revision |
| CO-4 | OWASP LLM02:2025 Sensitive Information Disclosure | OWASP Top 10 for LLM Applications 2025 | Voluntary benchmark | Identifier and title confirmed on genai.owasp.org |
| CO-5 | EU AI Act Art. 12, record-keeping | Regulation (EU) 2024/1689 | Legal applicability pending | Title confirmed on artificialintelligenceact.eu |
| CO-5 | IIA Standard 14.6, Engagement Documentation (legacy 2330) | Global Internal Audit Standards | Professional-practice reference | As for 4.2 |
| None | OWASP LLM06:2025 Excessive Agency | OWASP Top 10 for LLM Applications 2025 | Not applicable at runtime: the agent has no tools and runs no commands (section 4) | Identifier and title confirmed on genai.owasp.org |

EU AI Act high-risk classification would require an assessment under Article 6 and the relevant annexes. No such assessment has been done, and the audit-planning purpose stated in section 1 does not establish the outcome.

## 3. Acceptance criteria (testable, pass/fail)

Every criterion has a fixed number and one tag. `[code]` means a program can decide it exactly; `[llm]` means someone, or a model acting as judge, has to read the run. The agent calls a model at runtime either way. Each `[llm]` criterion has a check in `llm_checks.yaml`. A number stays with its criterion: a new criterion gets the next number, and a removed number is not used again. Section 6 gives each criterion's status and evidence. Where a criterion names a profile, it holds for that profile only.

*Numbering.* Before 2026-11-17 these criteria were numbered `CO<n>-AC<kk>` (for example `CO1-AC01`). They are now `CO-<n>.<k>` with no leading zero (`CO-1.1`); the order and the criteria are unchanged, so `CO3-AC07` is `CO-3.7`. Older issues and pull requests use the old form.

**CO-1 — Grounded scoping**

*Deterministic mapping*
- [code] **CO-1.1** — Given a US, Private, Healthcare, Cybersecurity profile, the mapping includes HIPAA.
- [code] **CO-1.2** — Given a US, Private, Healthcare, Financial Reporting profile, the mapping excludes SOX.
- [code] **CO-1.3** — Given a US, Private, Healthcare, Cybersecurity profile, `--dry-run` exits 0 and prints HIPAA.
- [code] **CO-1.4** — `--dry-run` makes no API call.
- [code] **CO-1.5** — Given a Germany, Financial Services, Public, Data Privacy profile, the mapping includes GDPR.
- [code] **CO-1.6** — Given a France, Financial Services, Public, Cybersecurity profile, the mapping includes DORA.
- [code] **CO-1.7** — A Dutch government body on a security topic gets BIO2.
- [code] **CO-1.8** — A non-Dutch government body does not get BIO2.
- [code] **CO-1.9** — A Dutch non-government entity does not get BIO2.
- [code] **CO-1.10** — A Dutch government body on a non-security topic does not get BIO2.
- [code] **CO-1.11** — A Dutch government body still gets the EU frameworks.
- [code] **CO-1.12** — Netherlands spellings still resolve to the EU jurisdiction group.

*Rationale and prompt*
- [code] **CO-1.13** — For a US, Technology, Private, IT General Controls profile, every `FrameworkMatch` has a non-empty rationale and full name.
- [code] **CO-1.14** — For any profile, every `FrameworkMatch` has a non-empty rationale.
- [code] **CO-1.15** — Every `framework_assessments[].applicability_rationale` in a report is non-empty. **Limitation:** the mapper's `FrameworkMatch.rationale` reaches the prompt and `--dry-run` only. The report carries the model's own `applicability_rationale`, and the schema accepts an empty string.
- [code] **CO-1.16** — The `PROVIDED FRAMEWORKS` section of the system prompt lists every mapped framework and no others. **Limitation:** the static role text and the schema descriptions name other frameworks as examples (`ISO-AC-01`, `SOX-ITGC-03`, `GDPR-PP-02`, `ISO 27001 A.8.3`), so the prompt as a whole is not limited to mapped names.
- [code] **CO-1.17** — The system prompt instructs the model not to reference frameworks outside that section.

*Membership, completeness, uniqueness*

`ComplianceAgent._check_grounding` compares `framework_assessments[].framework_name` and `mandatory_regulations[].regulation_name` against the mapped frameworks (case- and punctuation-insensitive; the full name, key, name before the dash, and abbreviations in the full name are accepted). It establishes membership only.

- [code] **CO-1.18** — A `framework_name` outside the mapped set is rejected with a `ComplianceReportError` carrying the raw response.
- [code] **CO-1.19** — A `regulation_name` outside the mapped set is rejected with a `ComplianceReportError`.
- [code] **CO-1.20** — The rejection happens in `ComplianceAgent.run`, not only in the check when called directly.
- [code] **CO-1.21** — The full name, a lower-case key and the name without its abbreviation are accepted for a mapped framework (tested on HIPAA). **Limitation:** a legitimate rewording outside the alias heuristic is rejected (fails closed).
- [code] **CO-1.22 (completeness)** — Every mapped framework is represented in `framework_assessments`, unless the specification defines and records an explicit exclusion.
- [code] **CO-1.23 (uniqueness)** — Every mapped framework is represented at most once in `framework_assessments`, after canonicalising accepted aliases.
- [llm] **CO-1.24** — `requirement_source` inside a mapped framework is correct. **Limitation:** names are matched, not clauses, so this check does not catch a wrong `requirement_source`.

*Clause references*
- [code] **CO-1.25** — Each `requirement_source` gets one `reference_checks` entry.
- [code] **CO-1.26** — Each `applicable_sections` entry gets one `reference_checks` entry. **Limitation:** clause numbers written in free text (`description`, `testing_approach`, `key_gaps`, `compliance_notes`, `executive_summary`) are not checked.
- [code] **CO-1.27** — Every entry has status `unverified` and a heuristic confidence below 1.0.
- [code] **CO-1.28** — A clause missing from a shipped list is flagged (`identifier_not_found`), and the report is still returned.
- [code] **CO-1.29** — A model-supplied `reference_checks` value is ignored, including a malformed one.
- [code] **CO-1.30** — A reference to a mapped framework with no shipped clause list is recorded as `framework_not_covered`. **Limitation:** clause lists exist for 10 of the 30 frameworks; the other 20 are not checked.
- [code] **CO-1.31** — Shipped clause lists are structurally valid and carry provenance.
- [code] **CO-1.32** — Shipped clause lists match the current official source text.
- **Limitation for all clause checks:** a match shows a clause exists, not that it says what the model claims.

**CO-2 — Valid output**

*Permitted processing versus prohibited repair*

The agent may perform the processing below. Each is deterministic and none of it invents substantive content, except where a limitation is noted.

| Processing | Where | Treatment |
|---|---|---|
| Strip `<think>` blocks from OpenAI-compatible responses | `openai_compatible.py` | Permitted extraction |
| Keep only the last text block of an Anthropic response | `anthropic_client.py` | Permitted extraction |
| Strip markdown fences; slice from the first `{` to the last `}` | `_extract_json_object` | Permitted extraction |
| Fill `report_id` and `generated_at` when absent | Pydantic defaults | Application-owned derivation. A model-supplied value is kept (CO-5.9) |
| Fill `audit_input` from the trusted input when missing or empty | `_parse_and_validate` | Application-owned derivation. A model-supplied value is kept at this commit (CO-5.10); open PR #51 changes this |
| Force `disclaimer` to the standard text | `_parse_and_validate` | Application-owned field |
| Drop model-supplied `reference_checks` and recompute them | `_parse_and_validate`, `run` | Application-owned field |
| Replace model-supplied `warnings` | `run` | Application-owned field |
| Convert `Critical` to `High`, truncate titles to 100 characters, deduplicate gaps | `saaf/output/findings.py` | Export transformation only. It applies to `--output findings`, after validation; it is not validation of the model response |
| Drop unknown top-level or nested fields | Pydantic default (`extra="ignore"`) | Current behaviour, recorded here so it is not read as strict rejection. Not reviewed as a design choice |
| Lax type coercion (for example `"yes"` to `True` for `mandatory`) | Pydantic default | Current behaviour, as above. A local probe confirmed `"yes"` is accepted |

Prohibited: inventing a missing substantive value, or returning a report after schema validation failed. `Critical` to `High` is not a repair of the model's report, because the JSON and terminal outputs keep the original rating.

*Criteria*
- [code] **CO-2.1** — A response wrapped in markdown fences is extracted and validated.
- [code] **CO-2.2** — A response surrounded by prose is extracted and validated.
- [code] **CO-2.3** — A response with no JSON object raises `ComplianceReportError` carrying the raw response.
- [code] **CO-2.4** — Valid JSON that is not an object (for example `[1, 2]` or `42`) raises `ComplianceReportError`.
- [code] **CO-2.5** — JSON with an invalid `risk_rating` raises `ComplianceReportError` carrying the raw response, and no report is returned.
- [code] **CO-2.6** — JSON with missing required fields raises `ComplianceReportError`.
- [code] **CO-2.7** — An invalid `--industry` makes the CLI exit non-zero with an argparse "invalid choice" error.
- [code] **CO-2.8** — An invalid `--listed-status` makes the CLI exit non-zero.
- [code] **CO-2.9** — An invalid listed status is rejected by `AuditInput`.
- [code] **CO-2.10** — An invalid `--audit-topic` makes the CLI exit non-zero.
- [code] **CO-2.11** — Those CLI rejections happen before any API call.
- [code] **CO-2.12** — A 4xx API error fails immediately, without retry.
- [code] **CO-2.13** — A 5xx error is retried up to `max_retries` and then fails with `ComplianceReportError`.
- [code] **CO-2.14** — A connection error is retried up to `max_retries` and then fails with `ComplianceReportError`.
- [code] **CO-2.15** — Each `--output findings` record has an `F-NN` id, a title of at most 100 characters, a rating in High/Medium/Low/Informational and the other required fields, checked against the field and enum lists copied into `tests/test_findings.py`.
- [code] **CO-2.16** — `Critical` is exported as `High`.
- [code] **CO-2.17** — Optional finding fields the report does not hold (root cause, impact, owner, target date, management response, evidence references) are omitted, not invented.
- [code] **CO-2.18** — Exported findings validate against `outputs/schemas/finding-schema.json`, which lives in SAAF-Project/SAAF-Project and is not vendored here.
- [code] **CO-2.19** — The agent completes a run against a local OpenAI-compatible server, with no key.
- [code] **CO-2.20** — An endpoint response not shaped like chat-completions raises a non-retryable `LLMError`.
- [code] **CO-2.21** — A non-JSON endpoint response raises `LLMError`.
- [code] **CO-2.22** — An explicit `Config` argument beats the matching environment variable.
- [code] **CO-2.23** — The CLI flags `--provider`, `--model` and `--base-url` reach `Config` as those explicit arguments. **Limitation:** an explicitly empty value cannot override the environment, because empty means "not supplied" (issue #40).

**CO-3 — Decision support, not conclusions**
- [code] **CO-3.1** — The rendered terminal report contains the disclaimer.
- [code] **CO-3.2** — The JSON output contains the disclaimer.
- [code] **CO-3.3** — A model response omitting `disclaimer` still yields the standard text.
- [code] **CO-3.4** — A model response rewriting `disclaimer` yields the standard text.
- [code] **CO-3.5** — `disclaimer` is absent from the model-facing schema.
- [code] **CO-3.6** — `--output findings` output carries the disclaimer. **Limitation:** each finding carries `ai_assisted: true`, but the export has no disclaimer.
- [llm] **CO-3.7** — The report does not state that the entity is compliant or non-compliant. **Limitation:** there is no check. The prompt asks for gaps "typical" for a profile and does not forbid a conclusion.
- [code] **CO-3.8** — An unrecognised country makes the agent log a warning and set `report.warnings`.
- [code] **CO-3.9** — An unrecognised country produces a stderr warning under `--dry-run`.
- [code] **CO-3.10** — The terminal report shows the warning.
- [code] **CO-3.11** — The JSON output carries the warning in `warnings`.
- [code] **CO-3.12** — A model-supplied `warnings` value is overwritten.
- [code] **CO-3.13** — A supported country produces no warning.
- **Limitation:** the warning only signals the gap and coverage was not extended. Canada, India and Japan resolve to known keys and do not trigger it, although Canada has only minimal matrix entries and India and Japan have no jurisdiction-specific matrix entries.

**CO-4 — Data and secrets**

*Keys and endpoints*
- [code] **CO-4.1** — With the default provider and no key set, `Config` raises a configuration error naming `ANTHROPIC_API_KEY`.
- [code] **CO-4.2** — With the `openai` provider on its default endpoint and no key, `Config` raises a configuration error.
- [code] **CO-4.3** — The `anthropic` provider still requires a key with a custom endpoint.
- [code] **CO-4.4** — The `openai` provider with a custom endpoint needs no key. **Limitation:** this applies to any custom endpoint, not only local servers, and issue #40 proposes replacing the rule.
- [code] **CO-4.5** — The CLI turns a missing key into a configuration error on stderr and exit code 1.
- [code] **CO-4.6** — `--dry-run` works with no key set.
- [code] **CO-4.7** — The CLI has no flag for the API key. **Limitation:** `Config(api_key=...)` accepts one from Python callers.
- [code] **CO-4.8** — A base URL that is not http(s), has no host, or embeds credentials is rejected.
- [code] **CO-4.9** — A plain `http://` base URL to a non-local host logs a warning; a loopback host does not.
- [code] **CO-4.10** — The OpenAI-compatible client does not follow redirects.
- [code] **CO-4.11** — The Anthropic client does not follow redirects. **Limitation, stated honestly:** it uses the SDK's default HTTP client, which follows them. In a local probe with `anthropic` 2.7.0 a 307 from one local server was followed to another; the second server received the POST and no `x-api-key` header. At the time of that probe the requirements allowed other SDK versions (`anthropic>=0.40.0`); they now pin `anthropic==2.9.0`, which has not been probed.
- [code] **CO-4.12** — No API keys or credentials are present in tracked files.
- **Limitation:** a custom endpoint receives the same engagement data and API key as the default one; the agent cannot vouch for what it does with them.

*Data sent to the model*
- [code] **CO-4.13** — The engagement-specific values included in the model request are limited to the five documented profile fields, subject to optional company-name substitution. The request also contains the system prompt, the mapped framework information and the jurisdiction derived from the country.
- [code] **CO-4.14** — A real run prints a stderr warning that `company_name` is sent verbatim.
- [code] **CO-4.15** — `--yes` and `--no-warn` suppress that warning.
- [code] **CO-4.16** — `--dry-run` prints no such warning.
- [code] **CO-4.17** — `--anonymise` passes the placeholder `Entity A` to the agent instead of the company name.
- [code] **CO-4.18** — `--alias NAME` implies anonymisation and passes `NAME`.
- **Limitation:** anonymisation is opt-in, the default still sends the real name, nothing enforces synthetic names, the alias is not checked for containing the real name, and the other four fields are still sent.

*What is stored and logged*

The guarantee concerns the **real name** in anonymised runs. The alias is expected in logs and must be read as a placeholder, not a secret.

| Destination | Default run | Anonymised run (`--anonymise` / `--alias`) |
|---|---|---|
| Model request | Real name | Alias |
| Agent logs (stderr, INFO) | Real name | Alias; real name absent |
| Audit trail `inputs.company_name` | `[REDACTED]`, or the real name with `--audit-trail-include-company` | `[REDACTED]`, or the alias with `--audit-trail-include-company` |
| Audit trail `raw_response` | Verbatim; may echo the name | Verbatim; the model only saw the alias |
| Local JSON and terminal output (`audit_input`) | Real name | Real name, restored locally |

- [code] **CO-4.19** — In an anonymised run, the local output shows the real name in `audit_input`.
- [code] **CO-4.20** — In an anonymised run, the agent logs contain the alias and not the real name.
- [code] **CO-4.21** — In a default run, the agent logs the real name at INFO to stderr.
- [code] **CO-4.22** — The structured company-name field in the audit trail is redacted by default. The raw response is not comprehensively redacted and may contain identifying information.
- [code] **CO-4.23** — `redact_company=False` keeps the name in the structured field.
- [code] **CO-4.24** — `--audit-trail-include-company` sets `redact_company=False`.

**CO-5 — Traceability**
- [code] **CO-5.1** — At default log level, stderr logs the input profile, mapped jurisdiction and framework keys, provider, model name and endpoint host, API duration, token counts, stop reason, and the resulting `report_id`.
- [code] **CO-5.2** — `ComplianceReport` fills `report_id`, `generated_at` and `disclaimer` by default.
- [code] **CO-5.3** — JSON output includes `report_id`, `generated_at` and `audit_input`.
- [code] **CO-5.4** — `--audit-trail-dir DIR` writes `DIR/<report_id>.json` for a successful run.
- [code] **CO-5.5** — The record holds provider, model, endpoint host, sanitised URL, max tokens, max retries, knowledge-base version, attempts, input token count and stop reason.
- [code] **CO-5.6** — The record holds inputs, framework keys, prompt SHA-256 and raw response.
- [code] **CO-5.7** — The record holds the timeout setting, the output token count and UTC start and finish timestamps.
- [code] **CO-5.8** — An endpoint URL's credentials, query string and fragment do not reach the record.
- [code] **CO-5.9** — `report_id` and `generated_at` are agent-generated. **Limitation, stated honestly:** both remain in the schema shown to the model, and a model-supplied value is kept. A local probe confirmed `report_id="model-chosen-id"` and `generated_at="1999-01-01"` survive `run`, and `report_id="../evil"` survived it too. With the audit trail enabled, such an id makes the write step refuse and log an error while the run continues (`TestAuditTrail.test_unsafe_report_id_not_written` covers the refusal; the run continuing is by inspection). A repeated `report_id` overwrites the earlier file (by inspection). This weakens attribution when the audit trail is relied on.
- [code] **CO-5.10** — `audit_input` in a report equals the trusted input. **Limitation:** a model-supplied `audit_input` is kept at this commit, so a report can describe another company. Open PR #51 changes this. The audit trail's `inputs` come from the trusted input regardless.
- [code] **CO-5.11** — A run that fails parsing, validation or grounding leaves a persistent record.
- **Limitation:** the audit trail is opt-in and off by default. Without it, logs go to stderr only and nothing is persisted. The prompt is stored only as a hash, computed over the unredacted prompt. The record omits `reference_checks`, the application commit and dependency versions. The recorded endpoint is what the client was configured to call; it does not prove which backend served the request, and the configured model identifier does not establish an immutable backend version.

## 4. Good output / never do

Section 3's criteria are what is tested. This section separates what the code enforces from what a correct output should contain but can currently lack.

**Enforced invariants** (at this commit the run fails, or the value is forced, if these do not hold)

| # | Invariant | Enforcement | Criterion |
|---|---|---|---|
| M-1 | ✓ [code] Framework and regulation names in a report resolve to the mapped set | `_check_grounding` raises | CO-1.18, CO-1.19, CO-1.20 |
| M-2 | ✓ [code] A returned report validates against the `ComplianceReport` Pydantic model | `_parse_and_validate` raises | CO-2.5 |
| N-1 | ✕ [code] No partial or schema-invalid report is returned | Same; a non-object JSON value crashes rather than returning a report (CO-2.4) | CO-2.5 |
| M-3 | ✓ [code] `disclaimer` holds the standard text | Forced after validation | CO-3.3, CO-3.4 |
| M-4 | ✓ [code] `warnings` and `reference_checks` are agent-written | Overwritten or dropped | CO-3.12, CO-1.29 |
| M-5 | ✓ [code] Each `requirement_source` and `applicable_sections` entry has a `reference_checks` entry, labelled `unverified`, with confidence below 1.0 | `check_references`, `ReferenceCheck.status`, `CONFIDENCE` | CO-1.25, CO-1.26, CO-1.27 |
| N-2 | ✕ [code] A clause in a shipped list is never presented as verified because it exists there | Status is always `unverified` | CO-1.27 |

**Quality requirements** (a correct output should meet these; the code does not currently guarantee them)

| # | Requirement | Why it can fail today | Criterion |
|---|---|---|---|
| N-3 | ✕ [llm] Must not invent frameworks, clauses or citations | Framework names are checked for membership and cited clauses for existence where a list ships. Whether a citation is correct is not checked, and 20 of 30 frameworks have no list. This requirement is not verified | CO-1.24, CO-1.30, CO-1.32 |
| M-6 | ✓ [code] Every mapped framework is assessed exactly once | Not implemented: zero, one or duplicate assessments pass | CO-1.22, CO-1.23 |
| M-7 | ✓ [code] Each framework carries a rationale for why it applies | The field is required but may be empty | CO-1.15 |
| M-8 | ✓ [llm] Control objectives carry a clause reference and a concrete testing approach | Fields are required strings; the content, and whether any objectives exist, is not checked | Not tested |
| M-9 | ✓ [llm] `gap_risk_summary` has a rating, prioritised actions and a plain-English summary | Fields are required; lists may be empty and prose quality is not checked | Not tested |
| N-4 | ✕ [llm] Must not present output as audit-ready or as a compliance conclusion | Prompt wording and the disclaimer only; no check on the text | CO-3.7 |
| M-10 | ✓ [code] `report_id`, `generated_at` and `audit_input` describe this run | Filled by default, but a model-supplied value is kept | CO-5.9, CO-5.10 |
| N-6 | ✕ [llm] Must not follow an instruction planted in the input (for example in the company name) | The mapping does not use `company_name` (by inspection), but the name is free text inside the user message and no run has tested what the model does with it | Not tested (see PR #63 in section 5) |
| N-7 | ✕ [llm] Must not break a rule its own system prompt sets (only mapped frameworks, required fields, allowed values) | Grounding and schema validation catch some breaches after the fact; the rest needs a judged run | CO-1.18, CO-1.19, CO-2.5 |
| N-5 | ✕ [code] Must not hard-code credentials | Process control: a blocking secret-scan workflow and a manual scan, not a runtime guarantee | CO-4.12 |

**Not applicable at runtime: command allowlist** (`regulatory/guardrails/allowed-commands.md`). `cli.py`, `config.py` and `saaf/` contain no `subprocess`, `os.system`, `os.popen`, `exec` or `eval` calls. Neither LLM client sends tool or function definitions; each sends a system and a user message only. The runtime therefore has no enforcement point, because it cannot execute commands. This is the basis for classifying the requirement as not applicable, and the policy file itself demonstrates nothing about the agent. The maintenance scripts in `tools/clause_sources/` are not part of the runtime; they are covered in the README and issue #49.

The primary output is a framework overview, not a findings list. `--output findings` exports the gaps as `outputs/schemas/finding-schema.json` findings (see Coverage gaps for what that export cannot express).

## 5. Coverage gaps

- **Output completeness and uniqueness are not checked.** `_check_grounding` tests membership only. Local probes at this commit show a response with no framework assessments, or with one of the 8 mapped frameworks, passing `run`, and three aliases of HIPAA producing three assessments. `TestGroundingCheck.test_mapped_names_accepted_in_variants` itself builds a report with two HIPAA assessments and expects acceptance.
- **Mapping completeness is capped.** `FrameworkMapper` keeps at most 8 matches. A framework listed in the regulatory matrix can be cut, after which the model is not told about it and `_check_grounding` would reject it. A local enumeration (7 matrix jurisdiction keys × 10 industries × 3 listed statuses × 9 topics, not a repository test) found 372 of 1,890 combinations losing at least one matrix-listed framework, for example `APRA_CPS234` for Australia, Financial Services, Public, Vendor Management.
- **Grounding check matches names only.** Alias matching is a heuristic over `full_name`, key and abbreviations; a legitimate model rewording not covered by it is rejected (fails closed).
- **Clause references are unverified (partly mitigated).** `requirement_source` and `applicable_sections` are model-generated. For frameworks with an official clause list (`saaf/knowledge/clause_data/`, see README) the agent checks that the cited clause *exists* and records the outcome per reference in `reference_checks` (label `unverified`, heuristic confidence score, never 1.0). That does not show the clause says what the model claims. The other 20 frameworks (including ISO 27001, SOC 2, PCI DSS, SOX, NERC CIP, APRA CPS 234, FATF, CSRD/ESRS and BIO2) are not checked; a not-found or unmapped reference is flagged, not rejected.
- **Model-controllable identifiers.** `report_id`, `generated_at` and `audit_input` are accepted from the model (CO-5.9, CO-5.10). Open PR #51 addresses `audit_input` only.
- **Non-object JSON crashes.** `[1, 2]` or `42` raises `AttributeError` from `list(data.keys())` rather than `ComplianceReportError`, and the CLI does not catch it. No report is produced (CO-2.4).
- **Redirect handling differs by provider** (CO-4.10, CO-4.11).
- **Findings export has no disclaimer** (CO-3.6).
- **Knowledge base is hand-maintained and mostly unreviewed.** `KB_VERSION` (0.2.0) and per-framework `last_reviewed` / `source` fields exist, but only GDPR, DORA, MiFID II and BIO2 have a `source` and only BIO2 has a `last_reviewed`; the rest are `None` until a person reviews them (issue #30). There is no process for regulatory change. Boundary cases (e.g. a fintech that may or may not be a credit institution under DORA) are listed as an open question in the plan and are not handled explicitly.
- **BIO2 coverage is structural only.** The BIO2 entry (v1.3) lists the ISO 27001/27002 structure, not BIO2's government-specific measures, so the agent cannot ground measure-level citations. Municipalities' status is not stated because the official sources disagree on timing. The Cyberbeveiligingswet is not a separate entry, and private suppliers contractually bound to BIO2 are not modelled (issue #35).
- **Limited jurisdiction coverage (partly mitigated).** The system prompt names US, EU, UK, Australia and Singapore. Other countries resolve to a generic jurisdiction and the output may be thin, and the user is warned in the CLI, log and report (CO-3). Coverage itself is not extended. The warning is not shown for Canada, India or Japan.
- **Findings export is a conversion, not a native output.** `--output findings` maps `Critical` to `High`, emits one finding per gap, and cannot link a recommendation to a single gap because the report does not do so: critical-gap findings carry the whole priority-action list. Root cause, impact, owner and target date are left out.
- **Real entity names are sent to the configured endpoint by default.** A warning and an opt-in alias exist (issue #12), but anonymisation is not the default and the alias is not checked for leaking the real name. Real-name restoration in `audit_input` means local output stays sensitive.
- **Audit trail is opt-in and partial.** Failed runs are not recorded, and the prompt is stored only as a hash (see section 7).
- **No live-model evidence.** See the evidence boundary at the top of this document. Output quality and JSON compliance are not evaluated for any provider. CI runs the unit suite on every PR (`Tests`, plus `Lint`, `Secret scan` and a `Clause sources e2e` job on a schedule and on relevant PRs).
- **Many criteria are verified by code inspection or a manual run only.** Section 6 marks each one.
- **The `[llm]` criteria have checks but no scored run.** `llm_checks.yaml` holds one check each for CO-1.24, CO-3.7, M-8, M-9, N-3, N-4, N-6 and N-7. None has been run against a traced real-model run, so those rows stay unverified. To trace and score runs, see section 7.
- **Dependencies are hash-pinned, but newer than the last probe.** `requirements.txt` and `requirements-dev.txt` are generated from `requirements.in` / `requirements-dev.in` with `uv pip compile --generate-hashes`: every package, transitive ones included, is pinned with its SHA-256 hashes (`anthropic==2.9.0`, `pydantic==2.14.3`, `rich==15.0.0`, `unittest-xml-reporting==4.0.0` are the direct ones). The suite passes on a hash-checked install. The local probes in section 6 (for example the Anthropic redirect behaviour in CO-4.11) ran at `anthropic` 2.7.0 and were not repeated. The hashes prove the file matches what PyPI served when it was generated; they do not vet the packages themselves, and nobody audits the lockfile diff except the reviewer of the pull request.
- **GitHub Actions in the older workflows are pinned to major tags, not commit SHAs.** `tests.yml`, `lint.yml` and `e2e-clauses.yml` use tags such as `@v7`; only `standards.yml` is pinned to SHAs.
- **No Session 10 guard is chosen yet.** The pull-request pipeline runs the tests, lint, secret scan and the standards check, but no runtime guard from Session 10.

**Proposed acceptance tests** (from the review; none is written in this revision)

| Area | Proposed test | Status at this commit |
|---|---|---|
| Framework coverage | A response omitting one mapped framework fails, if complete coverage is required | Coverage gap (CO-1.22). A decision on required coverage comes first |
| Alias handling | Two aliases for the same framework cannot create duplicate assessments | Coverage gap (CO-1.23). The existing variants test accepts duplicates |
| Prompt injection | An adversarial company name cannot expand the permitted framework set or override application-owned fields | Proposed. The mapping does not use `company_name` (by inspection). Open PR #63 adds regression tests |
| Entity-specific conclusions | A response asserting "the company is compliant" is detected, or explicitly remains an unverified quality failure | Coverage gap (CO-3.7). Remains an unverified quality failure |
| CLI validation | Parameterised tests cover every constrained CLI argument | Coverage gap. Only `--industry` is tested at CLI level |
| Findings export | Exported findings validate against the actual repository JSON schema | Coverage gap (CO-2.18) |
| Redaction | Company-name leakage is exercised in logs, raw responses, nested fields and error paths | Partly covered: the structured field and pre-call logs are tested (CO-4.22, CO-4.20). Raw responses, nested fields and error paths are a coverage gap |
| Observability | Documented log fields and CLI JSON metadata are asserted directly | Coverage gap (CO-5.1, CO-5.3) |
| Failure records | If introduced, audit records are verified for API, parsing, validation and grounding failures | Proposed, conditional on the feature (CO-5.11) |

## 6. Status / validation

Status is **Draft**.

**Run cited.** At commit `311496a`, in a throwaway `python:3.12-slim` container with `requirements-dev.txt` installed into a repo-local `.venv` as CI does (resolved `anthropic` 2.7.0, `pydantic` 2.14.3), with `ANTHROPIC_API_KEY=ci-dummy-key`: `python -m unittest discover -s tests` ran 202 tests, OK, 1 skipped (the live-source e2e module, which needs `SAAF_E2E=1`). `ruff check .` passed. The `Tests`, `Lint` and `Secret scan` workflows also succeeded on this commit (Tests run [42831450775](https://github.com/SAAF-Project/Compliance-Report-Generator/actions/runs/42831450775)); the test count above comes from the container run.

**Reading the table.** Implementation status says what the code does. A row is **Pass** only when the named test exercises that exact behaviour. **Not test-verified** means the behaviour was checked by code inspection, a manual run or a local probe, and no test asserts it. **Not met** means a probe or code inspection shows the criterion does not hold at this commit. **Unverified** means no check exists and there is no evidence either way. Local probes and manual runs were one-off checks in that container and are not repository tests. A passed test using mocks, stubs or a local server is evidence for the behaviour it exercises, and for nothing beyond it.

| Criterion | Implementation status | Verification method | Result | Evidence |
|---|---|---|---|---|
| CO-1.1 · US Healthcare Cybersecurity includes HIPAA | Implemented | Unit test (mapper) | Pass | `TestFrameworkMapper.test_us_healthcare_includes_hipaa` |
| CO-1.2 · US Private Healthcare Financial Reporting excludes SOX | Implemented | Unit test (mapper) | Pass | `TestFrameworkMapper.test_us_private_excludes_sox` |
| CO-1.3 · `--dry-run` exits 0 and prints HIPAA | Implemented | CLI subprocess test | Pass | `TestCliDryRun.test_dry_run_exits_zero`, `TestCliDryRun.test_dry_run_shows_frameworks` |
| CO-1.4 · `--dry-run` makes no API call | Implemented | Code inspection | Not test-verified | `cli.py` `main` returns before `Config` and the client are created |
| CO-1.5 · Germany Financial Services includes GDPR | Implemented | Unit test (mapper) | Pass | `TestFrameworkMapper.test_eu_finserv_includes_gdpr` |
| CO-1.6 · France Financial Services includes DORA | Implemented | Unit test (mapper) | Pass | `TestFrameworkMapper.test_eu_finserv_includes_dora` |
| CO-1.7 · Dutch government on security topics gets BIO2 | Implemented | Unit test (mapper) | Pass | `TestBio2Selection.test_dutch_government_gets_bio2_on_security_topics` |
| CO-1.8 · Non-Dutch government does not get BIO2 | Implemented | Unit test (mapper) | Pass | `TestBio2Selection.test_non_dutch_government_does_not_get_bio2` |
| CO-1.9 · Dutch non-government does not get BIO2 | Implemented | Unit test (mapper) | Pass | `TestBio2Selection.test_dutch_non_government_does_not_get_bio2` |
| CO-1.10 · Dutch government on non-security topics does not get BIO2 | Implemented | Unit test (mapper) | Pass | `TestBio2Selection.test_dutch_government_non_security_topics_do_not_get_bio2` |
| CO-1.11 · EU frameworks still apply to Dutch government | Implemented | Unit test (mapper) | Pass | `TestBio2Selection.test_eu_frameworks_still_apply_to_dutch_government` |
| CO-1.12 · Netherlands resolves to the EU group | Implemented | Unit test | Pass | `TestCountryKey.test_netherlands_still_resolves_to_the_eu_group` |
| CO-1.13 · Named profile has rationale on every match | Implemented | Unit test (mapper) | Pass | `TestFrameworkMapper.test_framework_matches_have_rationale` |
| CO-1.14 · Any profile has rationale on every match | Implemented | Code inspection | Not test-verified | `FrameworkMapper._collect_framework_matches` adds a rationale part at the topic step for every kept match. The test covers one profile |
| CO-1.15 · Report-level `applicability_rationale` is non-empty | Not implemented | Local probe | Not met | `FrameworkAssessment.applicability_rationale` has no length constraint; an empty value passed `run` |
| CO-1.16 · Prompt section lists every mapped framework and no others | Implemented | Unit test (partial), code inspection | Not test-verified | `TestSystemPromptBuilder.test_system_prompt_injects_framework_names` asserts only that at least one name appears. `_build_framework_section` iterates `framework_matches` |
| CO-1.17 · Prompt instructs the model to stay within that section | Implemented | Code inspection | Not test-verified | `_ROLE_SECTION` in `saaf/prompts/system_prompt.py` |
| CO-1.18 · Out-of-scope `framework_name` rejected | Implemented | Unit test (direct check) | Pass | `TestGroundingCheck.test_out_of_scope_framework_rejected_with_raw_response` |
| CO-1.19 · Out-of-scope `regulation_name` rejected | Implemented | Unit test (direct check) | Pass | `TestGroundingCheck.test_invented_regulation_rejected` |
| CO-1.20 · Rejected inside `run` | Implemented | Mocked agent test | Pass | `TestGroundingCheck.test_run_rejects_out_of_scope_framework_end_to_end` |
| CO-1.21 · HIPAA name variants accepted | Implemented | Unit test (direct check) | Pass | `TestGroundingCheck.test_mapped_names_accepted_in_variants` |
| CO-1.22 · Completeness | Not implemented | Local probe, code inspection | Not met | `_check_grounding` has no completeness logic; empty and one-framework reports passed `run` |
| CO-1.23 · Uniqueness | Not implemented | Local probe, unit test (contrary) | Not met | Three HIPAA aliases passed `run`; `TestGroundingCheck.test_mapped_names_accepted_in_variants` accepts duplicates |
| CO-1.24 · `requirement_source` correctness | Not implemented | None | Unverified | `_check_grounding` reads names only; see section 5 |
| CO-1.25 · One entry per `requirement_source` | Implemented | Mocked agent test | Pass | `TestAgentReferenceChecks.test_reference_checks_present_in_json_output` (four controls, four entries), `TestAgentReferenceChecks.test_every_reference_is_labelled_unverified_with_a_score` |
| CO-1.26 · One entry per `applicable_sections` entry | Implemented | Unit test | Pass | `TestCheckReferences.test_bare_clause_uses_parent_framework` |
| CO-1.27 · Status `unverified`, confidence below 1.0 | Implemented | Mocked agent test, unit test | Pass | `TestAgentReferenceChecks.test_every_reference_is_labelled_unverified_with_a_score`, `TestCheckReferences.test_all_confidences_below_one` |
| CO-1.28 · Missing clause flagged, report returned | Implemented | Unit test, mocked agent test | Pass | `TestCheckReferences.test_missing_article_not_found`, `TestAgentReferenceChecks.test_every_reference_is_labelled_unverified_with_a_score` |
| CO-1.29 · Model-supplied `reference_checks` ignored | Implemented | Mocked agent test | Pass | `TestAgentReferenceChecks.test_model_supplied_reference_checks_are_ignored`, `TestAgentReferenceChecks.test_malformed_model_supplied_reference_checks_do_not_fail_validation` |
| CO-1.30 · Framework with no list is `framework_not_covered` | Implemented | Unit test | Pass | `TestCheckReferences.test_framework_without_clause_list` |
| CO-1.31 · Shipped lists are well-formed with provenance | Implemented | Unit test | Pass | `TestShippedClauseData.test_every_list_has_provenance_and_identifiers`, `TestShippedClauseData.test_every_list_declares_granularity_and_rationale` |
| CO-1.32 · Shipped lists match current official text | Implemented | Weekly e2e workflow, not run here | Not test-verified | `.github/workflows/e2e-clauses.yml`; the module was skipped in the run cited |
| CO-2.1 · Fenced JSON extracted | Implemented | Mocked agent test | Pass | `TestAgentRunSuccess.test_markdown_fenced_json_is_extracted` |
| CO-2.2 · Prose-wrapped JSON extracted | Implemented | Mocked agent test | Pass | `TestAgentRunSuccess.test_prose_wrapped_json_is_extracted` |
| CO-2.3 · No JSON object raises with raw response | Implemented | Mocked agent test | Pass | `TestAgentRunInvalidOutput.test_no_json_raises_with_raw_response` |
| CO-2.4 · Non-object JSON raises `ComplianceReportError` | Not implemented | Local probe | Not met | `[1, 2]` and `42` raised `AttributeError` from `list(data.keys())` in `_parse_and_validate` |
| CO-2.5 · Invalid `risk_rating` raises, no report | Implemented | Mocked agent test | Pass | `TestAgentRunInvalidOutput.test_schema_invalid_json_raises_with_raw_response` |
| CO-2.6 · Missing required fields raise | Implemented | Local probe, code inspection | Not test-verified | Required fields in `ComplianceReport`; a probe response lacking them raised `ComplianceReportError`. No test names this case |
| CO-2.7 · Invalid `--industry` rejected by CLI | Implemented | CLI subprocess test | Pass | `TestCliDryRun.test_invalid_industry_rejected_by_cli` |
| CO-2.8 · Invalid `--listed-status` rejected by CLI | Implemented | Code inspection, manual run | Not test-verified | argparse `choices` in `build_parser`; exit 2 in a manual run |
| CO-2.9 · Invalid listed status rejected by `AuditInput` | Implemented | Unit test | Pass | `TestPydanticModels.test_invalid_listed_status_rejected` |
| CO-2.10 · Invalid `--audit-topic` rejected by CLI | Implemented | Code inspection, manual run | Not test-verified | argparse `choices` in `build_parser`; exit 2 in a manual run. No test at CLI or model level |
| CO-2.11 · CLI rejection precedes any API call | Implemented | Code inspection | Not test-verified | `parser.parse_args` is the first step of `main`; the CLI test asserts only exit and message |
| CO-2.12 · 4xx fails immediately | Implemented | Mocked agent test | Pass | `TestAgentRunApiErrors.test_4xx_fails_immediately_without_retry` |
| CO-2.13 · 5xx retried then fails | Implemented | Mocked agent test | Pass | `TestAgentRunApiErrors.test_5xx_retries_max_retries_then_fails` |
| CO-2.14 · Connection error retried then fails | Implemented | Mocked agent test | Pass | `TestAgentRunApiErrors.test_connection_error_retries_max_retries_then_fails` |
| CO-2.15 · Findings have required fields and enums (copied list) | Implemented | Unit test | Pass | `FindingsExportTests.test_stub_report`, `FindingsExportTests.test_pydantic_report` |
| CO-2.16 · `Critical` exported as `High` | Implemented | Unit test | Pass | `FindingsExportTests.test_pydantic_report` |
| CO-2.17 · Optional finding fields omitted | Implemented | Code inspection | Not test-verified | `report_to_findings` never sets them; the test only asserts keys are within the allowed set |
| CO-2.18 · Findings validate against the repository schema | Not implemented | None | Unverified | Schema is in another repository; no validator is used |
| CO-2.19 · Agent run against a local OpenAI-compatible server | Implemented | Local HTTP server test | Pass | `TestAgentCustomEndpoint.test_agent_runs_end_to_end_against_custom_endpoint` |
| CO-2.20 · Non-chat-completions response raises | Implemented | Local HTTP server test | Pass | `TestOpenAICompatibleClient.test_non_chat_completions_response_is_rejected` |
| CO-2.21 · Non-JSON endpoint response raises | Implemented | Local HTTP server test | Pass | `TestOpenAICompatibleClient.test_non_json_response_is_rejected` |
| CO-2.22 · Explicit `Config` argument beats environment | Implemented | Unit test | Pass | `TestConfigPrecedence.test_explicit_arguments_beat_env` |
| CO-2.23 · CLI flags reach `Config` | Implemented | Code inspection | Not test-verified | `Config(provider=args.provider or "", ...)` in `cli.py` |
| CO-3.1 · Disclaimer in rendered report | Implemented | Unit test | Pass | `TestDisclaimerNotOverridable.test_disclaimer_in_rendered_report` |
| CO-3.2 · Disclaimer in JSON | Implemented | Unit test | Pass | `TestDisclaimerNotOverridable.test_disclaimer_in_json_output` |
| CO-3.3 · Omitted disclaimer filled | Implemented | Unit test | Pass | `TestDisclaimerNotOverridable.test_omitted_disclaimer_gets_standard_text` |
| CO-3.4 · Rewritten disclaimer replaced | Implemented | Unit test | Pass | `TestDisclaimerNotOverridable.test_rewritten_disclaimer_is_replaced` |
| CO-3.5 · Schema hides disclaimer | Implemented | Unit test | Pass | `TestDisclaimerNotOverridable.test_schema_hides_disclaimer_from_model` |
| CO-3.6 · Findings export carries disclaimer | Not implemented | Code inspection | Not met | `report_to_findings` emits findings only |
| CO-3.7 · No compliance conclusion | Not implemented | None | Unverified | No check on output text; prompt wording only |
| CO-3.8 · Agent logs and sets report warning | Implemented | Mocked agent test | Pass | `TestJurisdictionWarning.test_agent_logs_and_sets_report_warning` |
| CO-3.9 · CLI stderr warning under `--dry-run` | Implemented | CLI subprocess test | Pass | `TestJurisdictionWarning.test_cli_dry_run_warns_on_stderr` |
| CO-3.10 · Terminal report shows warning | Implemented | Unit test | Pass | `TestJurisdictionWarning.test_formatter_renders_warning` |
| CO-3.11 · JSON `warnings` field | Implemented | Code inspection | Not test-verified | `report.warnings` is asserted on the object, not in serialised JSON |
| CO-3.12 · Model-supplied `warnings` overwritten | Implemented | Mocked agent test | Pass | `TestJurisdictionWarning.test_agent_overrides_model_supplied_warnings` |
| CO-3.13 · Supported country gives no warning | Implemented | Unit test, CLI subprocess test | Pass | `TestJurisdictionWarning.test_warning_none_for_supported`, `TestJurisdictionWarning.test_cli_no_warning_for_supported` |
| CO-4.1 · Default provider without key raises | Implemented | Unit test | Pass | `TestConfigDefaults.test_missing_anthropic_key_raises` |
| CO-4.2 · Hosted `openai` without key raises | Implemented | Unit test | Pass | `TestConfigProviders.test_openai_hosted_without_key_raises` |
| CO-4.3 · `anthropic` with custom endpoint needs key | Implemented | Unit test | Pass | `TestConfigProviders.test_anthropic_still_requires_key_with_custom_endpoint` |
| CO-4.4 · `openai` with custom endpoint needs no key | Implemented | Unit test | Pass | `TestConfigProviders.test_custom_endpoint_needs_no_key_for_openai_compatible` |
| CO-4.5 · CLI configuration error, exit 1 | Implemented | Code inspection, manual run | Not test-verified | `except EnvironmentError` in `cli.py` `main`; exit 1 in a manual run with no key |
| CO-4.6 · `--dry-run` with no key | Implemented | Code inspection, manual run | Not test-verified | `TestCliDryRun.test_dry_run_no_api_key_needed` sets a dummy key, so it does not exercise this; exit 0 in a manual run with no key |
| CO-4.7 · No CLI flag for the API key | Implemented | Code inspection | Not test-verified | `build_parser` in `cli.py` |
| CO-4.8 · Bad base URL rejected | Implemented | Unit test | Pass | `TestValidateBaseUrl.test_rejects_bad_scheme_missing_host_and_embedded_credentials`, `TestConfigPrecedence.test_invalid_base_url_raises_environment_error` |
| CO-4.9 · Plain http to non-local host warns | Implemented | Unit test | Pass | `TestValidateBaseUrl.test_plain_http_to_remote_host_warns_but_loopback_does_not` |
| CO-4.10 · OpenAI-compatible client does not follow redirects | Implemented | Local HTTP server test | Pass | `TestOpenAICompatibleClient.test_redirect_is_not_followed_so_the_key_is_not_forwarded` |
| CO-4.11 · Anthropic client does not follow redirects | Not implemented | Local probe | Not met | SDK default `follow_redirects=True` at `anthropic` 2.7.0; a local 307 was followed |
| CO-4.12 · No credentials in tracked files | Implemented as process control | Manual scan, CI workflow | Not test-verified | `git grep` at `311496a` for long `sk-` keys, `AKIA` keys and private-key headers: no matches; no tracked `.env`. `Secret scan` (gitleaks) succeeded on this commit |
| CO-4.13 · Request limited to the five fields | Implemented | Code inspection | Not test-verified | `build_user_message`; both clients send only system and user messages. No test asserts the absence of other values |
| CO-4.14 · Verbatim-name warning | Implemented | Mocked CLI test | Pass | `TestEntityNameDataFlow.test_default_warns_and_sends_real_name` |
| CO-4.15 · `--yes` / `--no-warn` suppress it | Implemented | Mocked CLI test | Pass | `TestEntityNameDataFlow.test_yes_suppresses_warning` |
| CO-4.16 · `--dry-run` prints no warning | Implemented | CLI in-process test | Pass | `TestEntityNameDataFlow.test_dry_run_does_not_warn` |
| CO-4.17 · `--anonymise` passes the alias | Implemented | Mocked CLI test | Pass | `TestEntityNameDataFlow.test_anonymise_sends_alias_not_real_name` |
| CO-4.18 · `--alias` implies anonymisation | Implemented | Mocked CLI test | Pass | `TestEntityNameDataFlow.test_alias_implies_anonymise` |
| CO-4.19 · Real name restored locally | Implemented | Mocked CLI test | Pass | `TestEntityNameDataFlow.test_anonymised_output_restores_real_name_locally` |
| CO-4.20 · Alias in logs, real name absent | Implemented | Mocked agent test | Pass | `TestEntityNameDataFlow.test_real_name_not_logged_when_anonymised` covers logs up to the API call. Later log lines by inspection |
| CO-4.21 · Default run logs the real name | Implemented | Code inspection | Not test-verified | `log.info("Starting audit: ...")` in `ComplianceAgent.run` |
| CO-4.22 · Structured name redacted; raw response verbatim | Implemented | Unit test | Pass | `TestAuditTrail.test_record_redacts_company_by_default` |
| CO-4.23 · `redact_company=False` keeps the name | Implemented | Unit test | Pass | `TestAuditTrail.test_company_kept_when_opted_in` |
| CO-4.24 · CLI flag sets `redact_company=False` | Implemented | Code inspection | Not test-verified | `AuditTrail(..., redact_company=not args.audit_trail_include_company)` in `cli.py` |
| CO-5.1 · Documented log fields | Implemented | Code inspection | Not test-verified | `log.info` calls in `saaf/core/agent.py`; no test asserts these lines |
| CO-5.2 · Report defaults fill identifiers | Implemented | Unit test | Pass | `TestPydanticModels.test_compliance_report_defaults` |
| CO-5.3 · JSON output includes identifiers and input | Implemented | Code inspection | Not test-verified | `report.model_dump_json` in `cli.py`; `TestPydanticModels.test_compliance_report_json_roundtrip` covers `report_id` at model level only |
| CO-5.4 · `<report_id>.json` written on success | Implemented | Mocked agent test, unit test | Pass | `TestAgentAuditTrailMetadata.test_record_names_provider_endpoint_settings_and_call_outcome`, `TestAuditTrail.test_record_redacts_company_by_default` |
| CO-5.5 · Provider, endpoint, max tokens and retries, KB version, attempts, input tokens, stop reason | Implemented | Unit test, mocked agent test | Pass | `TestProviderMetadata.test_records_provider_endpoint_settings_usage_and_kb_version`, `TestAgentAuditTrailMetadata.test_record_names_provider_endpoint_settings_and_call_outcome` |
| CO-5.6 · Inputs, framework keys, prompt hash, raw response | Implemented | Unit test | Pass | `TestAuditTrail.test_record_redacts_company_by_default` |
| CO-5.7 · Timeout setting, output tokens, UTC timestamps | Implemented | Code inspection | Not test-verified | `ComplianceAgent.run` and `write_audit_record` store them; no test asserts these fields |
| CO-5.8 · Endpoint secrets excluded | Implemented | Unit test | Pass | `TestProviderMetadata.test_credentials_and_query_never_reach_the_file`, `TestSanitizeEndpoint.test_strips_userinfo_query_fragment_and_trailing_slash` |
| CO-5.9 · `report_id` and `generated_at` agent-generated | Not implemented | Local probe | Not met | Model-supplied values survived `run`; only the write step refuses an unsafe id (`TestAuditTrail.test_unsafe_report_id_not_written`) |
| CO-5.10 · `audit_input` equals trusted input | Not implemented | Local probe | Not met | Model-supplied company name survived `run`; open PR #51 |
| CO-5.11 · Failed runs leave a record | Not implemented | Code inspection | Not met | `audit_trail.record` is called only after grounding passes |
| M-1 · Names resolve to the mapped set | Implemented | Same as CO-1.18, CO-1.19 | Pass | See CO-1.18, CO-1.19, CO-1.20 |
| M-2 · Returned report validates | Implemented | Same as CO-2.5 | Pass | See CO-2.5 |
| M-3 · Disclaimer holds the standard text | Implemented | Same as CO-3.3, CO-3.4 | Pass | See CO-3.3, CO-3.4 |
| M-4 · `warnings` and `reference_checks` agent-written | Implemented | Same as CO-3.12, CO-1.29 | Pass | See CO-3.12, CO-1.29 |
| M-5 · Reference-check entry per clause, `unverified` | Implemented | Same as CO-1.25 to CO-1.27 | Pass | See CO-1.25, CO-1.26, CO-1.27 |
| M-6 · Every mapped framework assessed exactly once | Not implemented | Same as CO-1.22, CO-1.23 | Not met | See CO-1.22, CO-1.23 |
| M-7 · Rationale on every framework | Partly implemented | Same as CO-1.15 | Not met | See CO-1.15: the schema accepts an empty string |
| M-8 · Clause reference and concrete testing approach | Partly implemented | `[llm]`, none run | Unverified | Fields are required strings; the content is not checked. `llm_checks.yaml` holds the check, no run has been scored |
| M-9 · `gap_risk_summary` complete and plain-English | Partly implemented | `[llm]`, none run | Unverified | Fields are required; lists may be empty. `llm_checks.yaml` holds the check, no run has been scored |
| M-10 · `report_id`, `generated_at`, `audit_input` describe this run | Not implemented | Same as CO-5.9, CO-5.10 | Not met | See CO-5.9, CO-5.10 |
| N-1 · No partial or schema-invalid report | Implemented | Same as CO-2.5; CO-2.4 is not met | Pass, with CO-2.4 open | See CO-2.5 and CO-2.4 |
| N-2 · Clause never presented as verified | Implemented | Same as CO-1.27 | Pass | See CO-1.27 |
| N-3 · No invented frameworks, clauses or citations | Partly implemented | `[llm]`, none run | Unverified | Membership (CO-1.18) and existence (CO-1.28) are checked; correctness is not (CO-1.24). `llm_checks.yaml` holds the check, no run has been scored |
| N-4 · Not presented as audit-ready or a conclusion | Partly implemented | `[llm]`, none run | Unverified | The disclaimer is forced (CO-3.3, CO-3.4); the rest is prompt wording (CO-3.7). `llm_checks.yaml` holds the check, no run has been scored |
| N-5 · No hard-coded credentials | Implemented as process control | Same as CO-4.12 | Not test-verified | See CO-4.12 |
| N-6 · Ignores instructions planted in the input | Unknown | `[llm]`, none run | Unverified | Not tested. `llm_checks.yaml` holds the check, no run has been scored |
| N-7 · Follows its system prompt | Partly implemented | `[llm]`, none run | Unverified | `llm_checks.yaml` holds the check, no run has been scored |

## 7. Observability

Today: Python `logging` (default INFO, configurable with `--log-level`) writes to stderr. It records the input profile (including the company name or alias, see CO-4), mapped frameworks, model and token settings, API duration, token counts, stop reason, retries and errors, and the report ID. DEBUG adds prompt sizes and parse details. Opt-in (`--audit-trail-dir`): a per-run JSON record named after `report_id` with provider, model, endpoint host, call settings, knowledge-base version, token usage and the raw response (see CO-5). Missing: records for failed runs, storage of the prompt text, persistent log storage by default, cost tracking, and application commit and dependency versions. Input includes the company name, which may be sensitive, so persistence would need a redaction decision.

To trace every model call and score real runs against these criteria, use the Orq.ai skills `/orq-otel-tracing` and `/orq-criteria-to-evals` (`saaf-project.orq.ai`); nothing is traced there yet.

Proposed, not existing: allocate the run identifier in the agent before the API call, record unsuccessful outcomes, and include application and dependency version provenance.
