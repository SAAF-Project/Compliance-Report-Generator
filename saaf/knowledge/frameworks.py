"""
Framework Registry — static knowledge base of audit/compliance frameworks.

Each entry describes:
  - full_name: official name
  - domains: control domains / chapters
  - audit_topics: which audit topics it covers ("*" = all)
  - industries: which industries it applies to ("*" = universal)
  - listed_status: which listing statuses trigger it ("*" = all)
  - jurisdictions: if present, limits to these canonical jurisdiction keys
  - extraterritorial: if True, applies to any org handling data from that region
  - description: brief explanation for the system prompt
  - filter_domains: if False, every domain reaches the prompt (no keyword filter)
"""

import json
from pathlib import Path

FRAMEWORK_REGISTRY: dict[str, dict] = {

    # ── Universal frameworks ──────────────────────────────────────────────

    "ISO_27001": {
        "full_name": "ISO/IEC 27001:2022 — Information Security Management",
        "description": (
            "The leading international standard for information security management systems (ISMS). "
            "Provides a systematic approach to managing sensitive information through people, "
            "processes, and IT. Annex A contains 93 controls across 4 themes."
        ),
        "domains": [
            "Information Security Policies",
            "Organisation of Information Security",
            "Human Resource Security",
            "Asset Management",
            "Access Control",
            "Cryptography",
            "Physical and Environmental Security",
            "Operations Security",
            "Communications Security",
            "System Acquisition, Development and Maintenance",
            "Supplier Relationships",
            "Information Security Incident Management",
            "Business Continuity Management",
            "Compliance",
        ],
        "audit_topics": ["Cybersecurity", "Data Privacy", "IT General Controls", "Vendor Management", "Business Continuity"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    "NIST_CSF": {
        "full_name": "NIST Cybersecurity Framework v2.0",
        "description": (
            "A voluntary framework of standards, guidelines, and best practices for managing "
            "cybersecurity risk. Version 2.0 adds a 'Govern' function and expanded supply-chain "
            "guidance. Widely used as a benchmark even outside the US."
        ),
        "domains": ["Govern", "Identify", "Protect", "Detect", "Respond", "Recover"],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Business Continuity", "Vendor Management"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    "COBIT": {
        "full_name": "COBIT 2019 — Control Objectives for Information and Related Technologies",
        "description": (
            "An IT governance and management framework from ISACA covering how IT should be "
            "directed, managed, and monitored. Widely used for IT General Controls audits and "
            "as a bridge between IT and financial/operational governance."
        ),
        "domains": [
            "Evaluate, Direct and Monitor (EDM)",
            "Align, Plan and Organise (APO)",
            "Build, Acquire and Implement (BAI)",
            "Deliver, Service and Support (DSS)",
            "Monitor, Evaluate and Assess (MEA)",
        ],
        "audit_topics": ["IT General Controls", "Financial Reporting", "Vendor Management", "Operational Risk"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    "ISO_22301": {
        "full_name": "ISO 22301:2019 — Business Continuity Management",
        "description": (
            "International standard for business continuity management systems (BCMS). "
            "Specifies requirements for planning, establishing, implementing, and improving "
            "a BCMS to protect against, reduce the likelihood of, and ensure recovery from "
            "disruptive incidents."
        ),
        "domains": [
            "Context of the Organisation",
            "Leadership and Commitment",
            "Planning (BIA, Risk Assessment)",
            "Support (Resources, Communication)",
            "Operation (BCMS Plans, Exercises)",
            "Performance Evaluation",
            "Improvement",
        ],
        "audit_topics": ["Business Continuity", "Operational Risk"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    "ISO_31000": {
        "full_name": "ISO 31000:2018 — Risk Management Guidelines",
        "description": (
            "Provides principles, framework, and process for managing risk across any "
            "organisation or sector. Commonly used as the overarching risk management "
            "standard alongside sector-specific frameworks."
        ),
        "domains": [
            "Principles",
            "Framework (Leadership, Integration, Design, Implementation, Evaluation)",
            "Process (Scope, Risk Assessment, Risk Treatment, Communication)",
        ],
        "audit_topics": ["Operational Risk", "Financial Reporting", "Business Continuity"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    # ── Data Privacy ──────────────────────────────────────────────────────

    "GDPR": {
        "full_name": "General Data Protection Regulation (EU) 2016/679",
        "description": (
            "EU/EEA regulation governing personal data processing. Applies to any organisation "
            "processing personal data of EU/EEA residents, regardless of where the organisation "
            "is based (extraterritorial reach). Key obligations include lawful basis, data subject "
            "rights, DPIAs, 72-hour breach notification, and DPAs with processors."
        ),
        "domains": [
            "Lawful Basis for Processing (Art. 6)",
            "Special Category Data (Art. 9)",
            "Data Subject Rights (Arts. 12–22)",
            "Data Protection by Design and Default (Art. 25)",
            "Records of Processing Activities — RoPA (Art. 30)",
            "Data Protection Impact Assessments — DPIA (Art. 35)",
            "Data Breach Notification — 72-hour rule (Art. 33–34)",
            "Data Processing Agreements / DPAs (Art. 28)",
            "International Data Transfers (Arts. 44–49)",
            "Data Protection Officer — DPO (Arts. 37–39)",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity", "Vendor Management"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE",
            "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
            "IS", "LI", "NO",  # EEA non-EU
        ],
        "extraterritorial": True,
    },

    "UK_GDPR": {
        "full_name": "UK GDPR & Data Protection Act 2018",
        "description": (
            "Post-Brexit UK equivalent of EU GDPR, retained in UK law. Almost identical in "
            "structure and obligations. Regulated by the ICO. Applies to processing of UK "
            "residents' personal data."
        ),
        "domains": [
            "Lawful Basis for Processing",
            "Data Subject Rights",
            "Data Protection by Design",
            "Data Protection Impact Assessments",
            "Breach Notification — 72-hour rule",
            "Data Processing Agreements",
            "International Data Transfers",
            "Data Protection Officer",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity", "Vendor Management"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": ["UK", "GB"],
        "extraterritorial": True,
    },

    "CCPA_CPRA": {
        "full_name": "California Consumer Privacy Act / California Privacy Rights Act (CCPA/CPRA)",
        "description": (
            "California state privacy law granting consumers rights over their personal information. "
            "CPRA (2023) strengthened CCPA, adding sensitive personal information rights, opt-out "
            "of sharing, and the California Privacy Protection Agency (CPPA)."
        ),
        "domains": [
            "Consumer Rights (Know, Delete, Opt-Out, Non-Discrimination)",
            "Sensitive Personal Information",
            "Data Minimisation and Retention",
            "Privacy Notice",
            "Vendor Contracts",
            "Security Obligations",
        ],
        "audit_topics": ["Data Privacy", "Vendor Management"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States"],
        "extraterritorial": True,
    },

    "PDPA_SG": {
        "full_name": "Personal Data Protection Act 2012 (Singapore)",
        "description": (
            "Singapore's primary data protection legislation, administered by the PDPC. "
            "Governs collection, use, and disclosure of personal data. 2021 amendments "
            "introduced mandatory breach notification, data portability, and higher penalties."
        ),
        "domains": [
            "Consent Obligation",
            "Purpose Limitation Obligation",
            "Notification Obligation",
            "Access and Correction Obligation",
            "Accuracy Obligation",
            "Protection Obligation",
            "Retention Limitation Obligation",
            "Transfer Limitation Obligation",
            "Mandatory Data Breach Notification",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": ["SG", "SGP", "Singapore"],
    },

    # ── Financial / Capital Markets ───────────────────────────────────────

    "SOX": {
        "full_name": "Sarbanes-Oxley Act 2002 (SOX)",
        "description": (
            "US federal law requiring public companies to implement and assess internal controls "
            "over financial reporting (ICFR). Section 302 requires CEO/CFO certification of "
            "financial statements. Section 404 requires management and auditor assessment of ICFR. "
            "IT General Controls (ITGCs) are critical to SOX compliance."
        ),
        "domains": [
            "Financial Statement Accuracy — CEO/CFO Certification (Sec. 302)",
            "Internal Control over Financial Reporting — ICFR (Sec. 404)",
            "Audit Committee Independence (Sec. 301)",
            "Document Retention (Sec. 802)",
            "Whistleblower Protections (Sec. 806)",
            "IT General Controls — Access, Change Management, Operations",
        ],
        "audit_topics": ["Financial Reporting", "IT General Controls"],
        "industries": [
            "Financial Services", "Technology", "Retail", "Energy",
            "Manufacturing", "Telecommunications", "Real Estate", "Healthcare",
        ],
        "listed_status": ["Public"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    "COSO": {
        "full_name": "COSO Internal Control — Integrated Framework (2013) & ERM (2017)",
        "description": (
            "The dominant framework for designing and evaluating internal controls, widely "
            "used in SOX compliance. The five components are Control Environment, Risk Assessment, "
            "Control Activities, Information & Communication, and Monitoring. The 2017 ERM "
            "framework integrates enterprise risk management with strategy."
        ),
        "domains": [
            "Control Environment",
            "Risk Assessment",
            "Control Activities",
            "Information and Communication",
            "Monitoring Activities",
            "Enterprise Risk Management (ERM 2017)",
        ],
        "audit_topics": ["Financial Reporting", "Operational Risk", "IT General Controls"],
        "industries": ["*"],
        "listed_status": ["Public", "Private"],
    },

    "MiFID_II": {
        "full_name": "Markets in Financial Instruments Directive II (MiFID II / MiFIR)",
        "description": (
            "EU legislation regulating investment firms and trading venues. Key requirements "
            "include best execution, transaction reporting, product governance, client "
            "categorisation, and inducements/conflicts of interest management."
        ),
        "domains": [
            "Client Categorisation",
            "Best Execution",
            "Transaction Reporting",
            "Product Governance",
            "Conflicts of Interest",
            "Inducements",
            "Record Keeping",
        ],
        "audit_topics": ["Financial Reporting", "Operational Risk"],
        "industries": ["Financial Services"],
        "listed_status": ["*"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "DE", "FR", "IE", "IT", "LU", "NL", "ES", "SE",
        ],
    },

    # ── Healthcare ────────────────────────────────────────────────────────

    "HIPAA": {
        "full_name": "Health Insurance Portability and Accountability Act (HIPAA)",
        "description": (
            "US federal law protecting the privacy and security of Protected Health Information "
            "(PHI). Applies to covered entities (healthcare providers, insurers, clearinghouses) "
            "and their business associates. The Security Rule mandates administrative, physical, "
            "and technical safeguards. HITECH (2009) strengthened penalties and breach notification."
        ),
        "domains": [
            "Privacy Rule — PHI Handling and Minimum Necessary",
            "Security Rule — Administrative Safeguards",
            "Security Rule — Physical Safeguards",
            "Security Rule — Technical Safeguards",
            "Breach Notification Rule",
            "Business Associate Agreements (BAAs)",
            "HITECH Act — Enhanced Penalties and EHR Incentives",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity", "Vendor Management"],
        "industries": ["Healthcare"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    "HITRUST_CSF": {
        "full_name": "HITRUST Common Security Framework (CSF)",
        "description": (
            "A certifiable framework that harmonises HIPAA, ISO 27001, NIST CSF, PCI DSS, "
            "and other standards for the healthcare industry. Provides a prescriptive, "
            "risk-based approach with three assurance levels (e1, i1, r2)."
        ),
        "domains": [
            "Access Control",
            "Audit Logging and Monitoring",
            "Configuration Management",
            "Contingency Planning",
            "Identification and Authentication",
            "Incident Management",
            "Risk Management",
            "Transmission Protection",
            "Wireless Protection",
        ],
        "audit_topics": ["Cybersecurity", "Data Privacy", "IT General Controls"],
        "industries": ["Healthcare"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    # ── Payment & Financial Data ──────────────────────────────────────────

    "PCI_DSS": {
        "full_name": "PCI DSS v4.0 — Payment Card Industry Data Security Standard",
        "description": (
            "Mandatory standard for any organisation that stores, processes, or transmits "
            "cardholder data (CHD). Published by the PCI SSC. Version 4.0 (2022) adds "
            "customised implementation options and stronger authentication requirements."
        ),
        "domains": [
            "Req 1–2: Network Security Controls and Secure Configurations",
            "Req 3–4: Account Data Protection and Cryptography",
            "Req 5–6: Malware Protection and Secure Software Development",
            "Req 7–9: Access Control and Physical Security",
            "Req 10–11: Logging, Monitoring, and Security Testing",
            "Req 12: Organisational Security and Policies",
        ],
        "audit_topics": ["Cybersecurity", "Data Privacy", "IT General Controls"],
        "industries": ["Financial Services", "Retail", "Technology", "Healthcare"],
        "listed_status": ["*"],
    },

    "GLBA": {
        "full_name": "Gramm-Leach-Bliley Act (GLBA) / FTC Safeguards Rule",
        "description": (
            "US law requiring financial institutions to explain data-sharing practices and "
            "protect customer NPI (non-public personal information). The FTC Safeguards Rule "
            "(updated 2023) requires a formal written information security programme with "
            "specific technical controls."
        ),
        "domains": [
            "Financial Privacy Rule — Notice and Opt-Out",
            "Safeguards Rule — Written Information Security Programme",
            "Safeguards Rule — Risk Assessment",
            "Safeguards Rule — Access Controls and Encryption",
            "Safeguards Rule — Incident Response",
            "Safeguards Rule — Vendor Oversight",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity", "Vendor Management"],
        "industries": ["Financial Services"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    # ── Technology & Cloud ────────────────────────────────────────────────

    "SOC2": {
        "full_name": "SOC 2 Type II — System and Organisation Controls",
        "description": (
            "AICPA attestation standard for service organisations, evaluating controls relevant "
            "to the Trust Services Criteria: Security (mandatory), Availability, Processing "
            "Integrity, Confidentiality, and Privacy. Type II covers a period (typically 12 months)."
        ),
        "domains": [
            "CC1: Control Environment",
            "CC2: Communication and Information",
            "CC3: Risk Assessment",
            "CC4: Monitoring Activities",
            "CC5: Control Activities",
            "CC6: Logical and Physical Access Controls",
            "CC7: System Operations",
            "CC8: Change Management",
            "CC9: Risk Mitigation",
        ],
        "audit_topics": ["Cybersecurity", "Data Privacy", "IT General Controls", "Vendor Management"],
        "industries": ["Technology", "Financial Services", "Healthcare"],
        "listed_status": ["*"],
    },

    "CSA_CCM": {
        "full_name": "Cloud Security Alliance — Cloud Controls Matrix (CCM) v4",
        "description": (
            "A cybersecurity control framework for cloud computing, providing a detailed "
            "understanding of security concepts and principles aligned to cloud service providers. "
            "Maps to ISO 27001, NIST CSF, PCI DSS, HIPAA, and other standards."
        ),
        "domains": [
            "Application and Interface Security",
            "Audit Assurance and Compliance",
            "Business Continuity Management and Operational Resilience",
            "Change Control and Configuration Management",
            "Data Security and Privacy Lifecycle Management",
            "Datacenter Security",
            "Encryption and Key Management",
            "Governance, Risk and Compliance",
            "Human Resources Security",
            "Identity and Access Management",
            "Infrastructure and Virtualisation Security",
            "Interoperability and Portability",
            "Logging and Monitoring",
            "Security Incident Management",
            "Supply Chain Management",
            "Threat and Vulnerability Management",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Vendor Management"],
        "industries": ["Technology", "Financial Services", "Healthcare"],
        "listed_status": ["*"],
    },

    # ── EU / Digital ──────────────────────────────────────────────────────

    "DORA": {
        "full_name": "Digital Operational Resilience Act (EU) 2022/2554",
        "description": (
            "EU regulation applicable from January 2025 requiring financial entities to strengthen "
            "ICT risk management, resilience testing, incident reporting, and third-party ICT "
            "provider oversight. Applies to banks, insurers, investment firms, payment institutions, "
            "and critical ICT providers serving them."
        ),
        "domains": [
            "ICT Risk Management Framework",
            "ICT-Related Incident Management and Reporting",
            "Digital Operational Resilience Testing (TLPT)",
            "ICT Third-Party Risk Management",
            "Information and Intelligence Sharing",
        ],
        "audit_topics": ["Cybersecurity", "Business Continuity", "Vendor Management", "IT General Controls"],
        "industries": ["Financial Services"],
        "listed_status": ["*"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE",
            "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        ],
    },

    "NIS2": {
        "full_name": "NIS2 Directive (EU) 2022/2555 — Network and Information Security",
        "description": (
            "EU directive applicable from October 2024 expanding cybersecurity requirements "
            "to a wider range of sectors and entities. Introduces stricter governance, "
            "incident reporting (24-hour initial / 72-hour detailed), supply chain security, "
            "and management body accountability."
        ),
        "domains": [
            "Risk Management Policies",
            "Incident Handling",
            "Business Continuity",
            "Supply Chain Security",
            "Network and Information System Security",
            "Policies on Cryptography",
            "Human Resources Security",
            "Multi-Factor Authentication",
            "Management Body Accountability",
        ],
        "audit_topics": ["Cybersecurity", "Business Continuity", "Vendor Management"],
        "industries": [
            "Energy", "Financial Services", "Healthcare", "Technology",
            "Manufacturing", "Telecommunications", "Government",
        ],
        "listed_status": ["*"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE",
            "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        ],
    },

    "EU_AI_ACT": {
        "full_name": "EU Artificial Intelligence Act — Regulation (EU) 2024/1689",
        "description": (
            "EU regulation on artificial intelligence with extraterritorial reach: it applies to "
            "providers placing AI systems on the EU market and to providers and deployers outside "
            "the EU whose system output is used in the EU. Requirements are risk-based; Articles "
            "9–15 and 17 set the requirements for high-risk AI systems, which apply only after a "
            "classification under Article 6 and Annexes I/III. Harmonised standards from "
            "CEN-CENELEC JTC 21 give a presumption of conformity only once cited in the Official "
            "Journal (OJEU). Of the standards mapped below, only EN 18286 (quality management "
            "system) is cited; the others are drafts (prEN) and must be presented as such. In "
            "November 2026 the Article 10 and 12–15 drafts were renumbered as the EN 18229 series; "
            "the former numbers are noted for traceability. Application dates of the high-risk "
            "obligations must be confirmed against the current consolidated text."
        ),
        # Filled in below from AI_ACT_STANDARDS_MAPPING
        "domains": [],
        "audit_topics": ["AI Governance"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE",
            "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        ],
        "extraterritorial": True,
    },

    "ISO_IEC_SC42": {
        "full_name": "ISO/IEC JTC 1/SC 42 — Artificial intelligence standards (incl. ISO/IEC 42001)",
        "description": (
            "The international AI standards of ISO/IEC JTC 1/SC 42, including the certifiable AI "
            "management system standard ISO/IEC 42001, AI risk management (ISO/IEC 23894), AI "
            "system impact assessment (ISO/IEC 42005), data quality (ISO/IEC 5259 series), bias, "
            "robustness, transparency, explainability and testing. Voluntary unless required by "
            "contract or regulation; not harmonised standards under the EU AI Act unless adopted "
            "and cited as EN standards. The catalogue below lists every published standard and "
            "every project under development, with its ISO stage. A project under development "
            "(reference with NP, AWI, WD, CD, DIS, FDIS, DTR or DTS, or a stage below 60.60) is "
            "not a standard yet: present it as a draft and never as a requirement."
        ),
        # Filled in below from saaf/knowledge/standards_data/ISO_IEC_SC42.json
        "domains": [],
        # The catalogue is the scope (issue #55): pass every entry to the prompt
        "filter_domains": False,
        "audit_topics": ["AI Governance"],
        "industries": ["*"],
        "listed_status": ["*"],
    },

    # ── Netherlands — government ─────────────────────────────────────────

    "BIO2": {
        "full_name": "Baseline Informatiebeveiliging Overheid 2 (BIO2) — Dutch Government Information Security Baseline",
        "description": (
            "The government-wide information security baseline of the Netherlands, covering the "
            "central government, provinces, municipalities and water boards. BIO2 v1.3 was published "
            "in Staatscourant 2026, 7416 (in force 5 March 2026, replacing v1.04) and was established "
            "by the Overheidsbreed Beleidsoverleg Digitale Overheid (OBDO) on 23 September 2025. "
            "Part 1 (BIO2-kader) is structured according to ISO/IEC 27001:2023; part 2 "
            "(BIO-overheidsmaatregelen) is structured according to ISO/IEC 27002:2022 and adds "
            "government-specific measures. It replaces the three fixed baseline security levels of "
            "BIO 1 with an explicitly risk-driven approach. It is mandatory self-regulation for the "
            "central government, provinces and water boards; for organisations in scope of the "
            "Cyberbeveiligingswet (the Dutch NIS2 implementation, in force 15 August 2026) applying "
            "the BIO2 measures is a legal obligation. Cite ISO 27001/27002 structure only: the "
            "government-specific measure numbers are not part of the provided knowledge."
        ),
        "domains": [
            "Context, Scope and Leadership — ISMS scope, policy, roles and management commitment",
            "Risk Assessment and Treatment — risk-driven selection of security measures",
            "Support, Awareness and Documented Information",
            "Performance Evaluation and Improvement — monitoring, internal audit, corrective action",
            "Organisational Controls — policies, roles, access control, supplier relationships, incident management, continuity, compliance",
            "People Controls — screening, awareness, terms of employment, remote working",
            "Physical Controls — secure areas, equipment security, media handling",
            "Technological Controls — endpoint security, authentication, cryptography, logging and monitoring, network security, secure development, vulnerability management",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Vendor Management", "Business Continuity"],
        "industries": ["Government"],
        "listed_status": ["*"],
        "jurisdictions": ["NL"],
    },

    # ── Energy & Critical Infrastructure ─────────────────────────────────

    "NERC_CIP": {
        "full_name": "NERC CIP — Critical Infrastructure Protection Standards",
        "description": (
            "Mandatory reliability standards for bulk electric systems in North America. "
            "CIP-002 through CIP-014 cover asset identification, security management, "
            "personnel training, electronic security perimeters, physical security, "
            "incident reporting, recovery plans, and supply chain risk."
        ),
        "domains": [
            "CIP-002: BES Cyber System Categorisation",
            "CIP-003: Security Management Controls",
            "CIP-004: Personnel and Training",
            "CIP-005: Electronic Security Perimeters",
            "CIP-006: Physical Security",
            "CIP-007: Systems Security Management",
            "CIP-008: Incident Reporting",
            "CIP-009: Recovery Plans",
            "CIP-010: Configuration Change Management",
            "CIP-011: Information Protection",
            "CIP-013: Supply Chain Risk Management",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Vendor Management"],
        "industries": ["Energy"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States", "CA", "Canada"],
    },

    # ── Government / Federal ──────────────────────────────────────────────

    "NIST_800_53": {
        "full_name": "NIST SP 800-53 Rev 5 — Security and Privacy Controls",
        "description": (
            "Comprehensive catalogue of security and privacy controls for US federal information "
            "systems, required by FISMA. Also widely adopted in critical infrastructure and "
            "defence contracting. Organised into 20 control families."
        ),
        "domains": [
            "Access Control (AC)",
            "Audit and Accountability (AU)",
            "Awareness and Training (AT)",
            "Configuration Management (CM)",
            "Contingency Planning (CP)",
            "Identification and Authentication (IA)",
            "Incident Response (IR)",
            "Maintenance (MA)",
            "Media Protection (MP)",
            "Personnel Security (PS)",
            "Risk Assessment (RA)",
            "System and Communications Protection (SC)",
            "System and Information Integrity (SI)",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Business Continuity"],
        "industries": ["Government", "Technology", "Energy"],
        "listed_status": ["Government", "Public"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    "CMMC": {
        "full_name": "Cybersecurity Maturity Model Certification (CMMC) 2.0",
        "description": (
            "US Department of Defense framework requiring defence contractors to implement "
            "and certify cybersecurity controls. Level 1 (17 practices), Level 2 (110 practices "
            "aligned to NIST 800-171), Level 3 (additional NIST 800-172 practices)."
        ),
        "domains": [
            "Access Control",
            "Awareness and Training",
            "Audit and Accountability",
            "Configuration Management",
            "Identification and Authentication",
            "Incident Response",
            "Maintenance",
            "Media Protection",
            "Personnel Security",
            "Physical Protection",
            "Risk Assessment",
            "Security Assessment",
            "System and Communications Protection",
            "System and Information Integrity",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls", "Vendor Management"],
        "industries": ["Manufacturing", "Technology", "Government"],
        "listed_status": ["*"],
        "jurisdictions": ["US", "USA", "United States"],
    },

    # ── Australia ─────────────────────────────────────────────────────────

    "APRA_CPS234": {
        "full_name": "APRA CPS 234 — Information Security (Australia)",
        "description": (
            "Prudential standard from APRA (Australian Prudential Regulation Authority) "
            "requiring APRA-regulated entities (banks, insurers, super funds) to maintain "
            "information security capability and notify APRA of material incidents."
        ),
        "domains": [
            "Information Security Capability",
            "Policy Framework",
            "Information Asset Identification and Classification",
            "Implementation of Controls",
            "Incident Management",
            "Testing Control Effectiveness",
            "Internal Audit",
            "APRA Notification",
        ],
        "audit_topics": ["Cybersecurity", "IT General Controls"],
        "industries": ["Financial Services"],
        "listed_status": ["*"],
        "jurisdictions": ["AU", "AUS", "Australia"],
    },

    "AU_PRIVACY_ACT": {
        "full_name": "Privacy Act 1988 (Australia) — Australian Privacy Principles (APPs)",
        "description": (
            "Australian federal privacy law applying to organisations with annual turnover > "
            "AUD 3M and all health service providers. 13 Australian Privacy Principles (APPs) "
            "cover collection, use, disclosure, and security of personal information. "
            "2023 amendments propose stronger enforcement and a right to erasure."
        ),
        "domains": [
            "APP 1: Open and Transparent Management",
            "APP 3: Collection of Solicited Personal Information",
            "APP 5: Notification of Collection",
            "APP 6: Use and Disclosure",
            "APP 7: Direct Marketing",
            "APP 8: Cross-Border Disclosure",
            "APP 11: Security of Personal Information",
            "APP 12: Access to Personal Information",
            "APP 13: Correction of Personal Information",
            "Notifiable Data Breaches (NDB) Scheme",
        ],
        "audit_topics": ["Data Privacy", "Cybersecurity"],
        "industries": ["*"],
        "listed_status": ["*"],
        "jurisdictions": ["AU", "AUS", "Australia"],
    },

    # ── Anti-Money Laundering ─────────────────────────────────────────────

    "FATF_AML": {
        "full_name": "FATF Recommendations — Anti-Money Laundering / Counter-Terrorist Financing",
        "description": (
            "International standards from the Financial Action Task Force (FATF) on AML/CFT. "
            "Translated into local law (e.g. Bank Secrecy Act / FinCEN in the US, POCA in the UK, "
            "AML-CTF Act in Australia). Requires risk-based customer due diligence, transaction "
            "monitoring, suspicious activity reporting, and record-keeping."
        ),
        "domains": [
            "Risk-Based Approach",
            "Customer Due Diligence (CDD) and KYC",
            "Enhanced Due Diligence (EDD) for High-Risk Customers",
            "Beneficial Ownership Identification",
            "Ongoing Monitoring",
            "Suspicious Activity / Transaction Reporting (SAR/STR)",
            "Record Keeping",
            "Sanctions Screening",
            "Training and Compliance Programme",
        ],
        "audit_topics": ["Anti-Money Laundering"],
        "industries": ["Financial Services"],
        "listed_status": ["*"],
    },

    # ── ESG ───────────────────────────────────────────────────────────────

    "CSRD_ESRS": {
        "full_name": "EU Corporate Sustainability Reporting Directive (CSRD) / ESRS",
        "description": (
            "EU directive requiring large and listed companies to report on sustainability "
            "using European Sustainability Reporting Standards (ESRS). Applies from 2024 "
            "(large PIEs) to 2028 (SMEs). Requires double materiality assessment, limited "
            "assurance, and tagging in XBRL."
        ),
        "domains": [
            "Double Materiality Assessment",
            "General Disclosures (ESRS 2)",
            "Climate Change (E1)",
            "Pollution (E2), Water (E3), Biodiversity (E4), Circular Economy (E5)",
            "Own Workforce (S1), Value Chain Workers (S2)",
            "Business Conduct (G1)",
            "Digital Tagging and Assurance",
        ],
        "audit_topics": ["ESG & Sustainability", "Financial Reporting"],
        "industries": [
            "Financial Services", "Energy", "Manufacturing", "Retail",
            "Technology", "Telecommunications", "Real Estate",
        ],
        "listed_status": ["Public"],
        "jurisdictions": [
            "EU", "EEA", "AT", "BE", "DE", "FR", "IE", "IT", "LU", "NL", "ES", "SE",
        ],
    },

    "GRI": {
        "full_name": "GRI Standards — Global Reporting Initiative",
        "description": (
            "The most widely used global sustainability reporting framework. GRI Standards "
            "enable organisations to report on their economic, environmental, and social impacts. "
            "Often used alongside CSRD/ESRS and TCFD. Updated Universal Standards (GRI 1, 2, 3) "
            "effective 2023."
        ),
        "domains": [
            "GRI 1: Foundation (Reporting Principles)",
            "GRI 2: General Disclosures (Governance, Strategy)",
            "GRI 3: Material Topics",
            "Economic Standards (200 series)",
            "Environmental Standards (300 series — Emissions, Energy, Water, Waste)",
            "Social Standards (400 series — Employment, Health & Safety, Human Rights)",
        ],
        "audit_topics": ["ESG & Sustainability"],
        "industries": ["*"],
        "listed_status": ["Public", "Private"],
    },

    "TCFD": {
        "full_name": "TCFD — Task Force on Climate-related Financial Disclosures",
        "description": (
            "Framework for disclosing climate-related financial risks and opportunities "
            "across four pillars: Governance, Strategy, Risk Management, and Metrics & Targets. "
            "Now incorporated into IFRS S2 (climate) and CSRD/ESRS E1. Mandatory in UK and "
            "increasingly required globally."
        ),
        "domains": [
            "Governance — Board and Management Oversight of Climate Risk",
            "Strategy — Climate Scenarios and Business Impact",
            "Risk Management — Identification, Assessment, Integration",
            "Metrics and Targets — GHG emissions (Scope 1, 2, 3)",
        ],
        "audit_topics": ["ESG & Sustainability", "Financial Reporting"],
        "industries": ["Financial Services", "Energy", "Manufacturing", "Retail", "Technology"],
        "listed_status": ["Public"],
    },
}


# ── Knowledge-base metadata (issue #9) ────────────────────────────────────
#
# KB_VERSION identifies the hand-maintained knowledge base content. Bump it
# whenever framework or regulation entries change.
KB_VERSION = "0.4.0"

# Per-framework provenance. Keys:
#   last_reviewed: ISO date (YYYY-MM-DD) a maintainer last verified the entry
#                  against its source, or None if never reviewed.
#   source:        canonical official URL or citation, or None if not yet
#                  confirmed. Only fill in values that have been verified.
_FRAMEWORK_METADATA: dict[str, dict] = {
    "GDPR": {"source": "https://eur-lex.europa.eu/eli/reg/2016/679/oj"},
    "DORA": {"source": "https://eur-lex.europa.eu/eli/reg/2022/2554/oj"},
    "MiFID_II": {"source": "https://eur-lex.europa.eu/eli/dir/2014/65/oj"},
    # Checked against the Staatscourant publication on 2026-10-06 (issue #35)
    "BIO2": {
        "source": "https://zoek.officielebekendmakingen.nl/stcrt-2026-7416-n1.html",
        "last_reviewed": "2026-10-06",
    },
    # Not yet reviewed by a maintainer (issue #57); the date the standards
    # mapping was retrieved is AI_ACT_STANDARDS_REVIEWED below
    "EU_AI_ACT": {
        "source": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        "last_reviewed": None,
    },
    # Catalogue retrieved from ISO Open Data; no maintainer review yet (issue #55)
    "ISO_IEC_SC42": {
        "source": "https://www.iso.org/committee/6794475/x/catalogue/p/1/u/1/w/0/d/0",
        "last_reviewed": None,
    },
}

# ── EU AI Act harmonised standards mapping (issue #57) ────────────────────
#
# Which CEN-CENELEC JTC 21 standards support which high-risk requirement of
# the AI Act. Source: the AI Act standards map (https://ai-act-standards.com/,
# NoLeFa project), checked 2026-11-17, which follows prEN 18286 Annex B, the
# draft Annex ZA tables and the CEN-CENELEC project scopes. Stages are CEN
# stage codes: 20 working draft, 40 enquiry, 60 published. Only a standard
# with cited=True gives a presumption of conformity. Update the stages, the
# citation status and AI_ACT_STANDARDS_REVIEWED together.
AI_ACT_STANDARDS_REVIEWED = "2026-11-17"
AI_ACT_STANDARDS_SOURCE = "https://ai-act-standards.com/"

AI_ACT_STANDARDS: dict[str, dict] = {
    "EN 18286": {
        "title": "Quality management system for EU AI Act regulatory purposes",
        "stage": 60, "cited": True,
    },
    "prEN 18228": {"title": "AI risk management", "stage": 40, "cited": False},
    "prEN 18229-1": {
        "title": "AI system requirements — Part 1: Quality and governance of data sets in AI",
        "stage": 20, "cited": False, "formerly": "prEN 18284",
    },
    "prEN 18229-2": {
        "title": "AI system requirements — Part 2: Concepts, measures and requirements for managing bias in AI systems",
        "stage": 40, "cited": False, "formerly": "prEN 18283",
    },
    "prEN 18229-3": {
        "title": "AI system requirements — Part 3: Logging",
        "stage": 40, "cited": False, "formerly": "prEN 18229-1",
    },
    "prEN 18229-4": {
        "title": "AI system requirements — Part 4: Transparency",
        "stage": 20, "cited": False, "formerly": "prEN 18229-2",
    },
    "prEN 18229-5": {
        "title": "AI system requirements — Part 5: Human oversight",
        "stage": 40, "cited": False, "formerly": "prEN 18229-3",
    },
    "prEN 18229-6": {
        "title": "AI system requirements — Part 6: Accuracy",
        "stage": 20, "cited": False, "formerly": "prEN 18229-4",
    },
    "prEN 18229-7": {
        "title": "AI system requirements — Part 7: Robustness",
        "stage": 20, "cited": False, "formerly": "prEN 18229-5",
    },
    "prEN 18229-8": {
        "title": "AI system requirements — Part 8: Cybersecurity specifications for AI systems",
        "stage": 40, "cited": False, "formerly": "prEN 18282",
    },
}

# AI Act article -> (article title, supporting standards)
AI_ACT_STANDARDS_MAPPING: dict[str, tuple[str, list[str]]] = {
    "Art. 9": ("Risk management system", ["prEN 18228"]),
    "Art. 10": ("Data and data governance", ["prEN 18229-1", "prEN 18229-2"]),
    "Art. 11": ("Technical documentation", ["EN 18286", "prEN 18229-4"]),
    "Art. 12": ("Record-keeping", ["prEN 18229-3"]),
    "Art. 13": ("Transparency and provision of information to deployers", ["prEN 18229-4"]),
    "Art. 14": ("Human oversight", ["prEN 18229-5"]),
    "Art. 15": ("Accuracy, robustness and cybersecurity", ["prEN 18229-6", "prEN 18229-7", "prEN 18229-8"]),
    "Art. 17": ("Quality management system", ["EN 18286"]),
}

_STAGE_NAMES = {20: "working draft", 40: "enquiry", 60: "published"}


def _standard_label(code: str) -> str:
    std = AI_ACT_STANDARDS[code]
    if std["cited"]:
        status = "cited in the OJEU"
    else:
        stage = std["stage"]
        status = f"draft, stage {stage} {_STAGE_NAMES.get(stage, '')}".rstrip() + ", not cited"
    former = f", formerly {std['formerly']}" if std.get("formerly") else ""
    return f"{code} {std['title']} ({status}{former})"


def ai_act_domains() -> list[str]:
    """One control domain per AI Act article, naming the standards that support it."""
    return [
        f"AI Act {article} {title} — " + "; ".join(_standard_label(c) for c in codes)
        for article, (title, codes) in AI_ACT_STANDARDS_MAPPING.items()
    ]


FRAMEWORK_REGISTRY["EU_AI_ACT"]["domains"] = ai_act_domains()

# ── ISO/IEC JTC 1/SC 42 standards catalogue (issue #55) ───────────────────
#
# Every SC 42 deliverable that is published or under development, from the
# ISO Open Data export. Generated by tools/standards_sources/iso_sc42.py;
# regenerate it rather than editing the JSON by hand.
ISO_SC42_DATA_FILE = Path(__file__).parent / "standards_data" / "ISO_IEC_SC42.json"
ISO_SC42_CATALOGUE: dict = json.loads(ISO_SC42_DATA_FILE.read_text(encoding="utf-8"))
ISO_SC42_STANDARDS: list[dict] = ISO_SC42_CATALOGUE["standards"]


def _iso_label(std: dict) -> str:
    if std["status"] == "published":
        status = "published, under revision" if std["under_revision"] else "published"
    else:
        status = f"under development, stage {std['stage']}, not a published standard"
    return f"{std['reference']} {std['title']} ({status})"


def iso_sc42_domains() -> list[str]:
    """One domain per SC 42 deliverable, published ones first."""
    return [_iso_label(s) for s in ISO_SC42_STANDARDS]


FRAMEWORK_REGISTRY["ISO_IEC_SC42"]["domains"] = iso_sc42_domains()

for _key, _entry in FRAMEWORK_REGISTRY.items():
    _meta = _FRAMEWORK_METADATA.get(_key, {})
    _entry.setdefault("last_reviewed", _meta.get("last_reviewed"))
    _entry.setdefault("source", _meta.get("source"))
del _key, _entry, _meta
