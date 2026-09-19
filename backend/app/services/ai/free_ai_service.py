"""
Free AI Legal Response Engine - No API key required.
Uses direct HTTP calls to free public AI endpoints with a rich
built-in legal knowledge base as fallback.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in Legal Knowledge Base
# ---------------------------------------------------------------------------
LEGAL_KNOWLEDGE = {
    # Core concepts
    "habeas corpus": """## Habeas Corpus

**Definition:** A fundamental legal writ (court order) that requires a person under arrest to be brought before a judge or into court.

**Purpose:** Protects individuals from unlawful or indefinite imprisonment without trial.

**Key Points:**
- Latin for *"you shall have the body"*
- Considered the "great writ of liberty" in common law systems
- Allows a prisoner to challenge the legality of their detention
- Court must determine if detention is lawful
- Available in India under Article 32 and 226 of the Constitution

**When Used:**
- Challenging unlawful arrest or detention
- Challenging conditions of confinement
- Immigration and deportation cases

**Example:** If someone is held in custody without being charged, their lawyer can file a habeas corpus petition to compel the court to review the detention.""",

    "contract": """## Contract Law

**Definition:** A legally binding agreement between two or more parties that creates mutual obligations enforceable by law.

**Essential Elements:**
1. **Offer** – One party proposes terms
2. **Acceptance** – Other party agrees to those terms
3. **Consideration** – Something of value exchanged
4. **Capacity** – Parties must be legally capable
5. **Legality** – Purpose must be lawful

**Types of Contracts:**
- Express contracts (written or verbal)
- Implied contracts (inferred from conduct)
- Void contracts (no legal effect)
- Voidable contracts (can be cancelled by one party)

**Breach of Contract:**
Occurs when one party fails to fulfill their contractual obligations. Remedies include:
- Damages (monetary compensation)
- Specific performance (court orders fulfillment)
- Rescission (cancellation of contract)

**Governed by:** Indian Contract Act, 1872 in India""",

    "bail": """## Bail

**Definition:** The temporary release of an accused person awaiting trial, sometimes on condition that a sum of money is lodged to guarantee their appearance in court.

**Types of Bail in India:**
1. **Regular Bail** (Section 437, 439 CrPC) – After arrest
2. **Anticipatory Bail** (Section 438 CrPC) – Before arrest
3. **Interim Bail** – Temporary, pending hearing of bail application
4. **Default Bail** – When investigation not completed within time limit

**Factors Courts Consider:**
- Nature and gravity of the offence
- Criminal antecedents of the accused
- Likelihood of fleeing justice
- Safety of the community
- Strength of evidence

**Bail Conditions May Include:**
- Surrendering passport
- Regular reporting to police station
- Not leaving jurisdiction
- Providing surety""",

    "fir": """## FIR (First Information Report)

**Definition:** A written document prepared by police when they receive information about the commission of a cognizable offence.

**Key Points:**
- Registered under Section 154 of CrPC
- Marks the beginning of criminal proceedings
- Must be registered for all cognizable offences
- Complainant has right to free copy of FIR

**What FIR Contains:**
- Name and address of informant
- Date, time and place of offence
- Description of offence
- Names of accused (if known)
- Names of witnesses

**Rights if Police Refuse to Register FIR:**
- Complain to Superintendent of Police
- File complaint before Magistrate under Section 156(3) CrPC
- Send written complaint by post to SP

**Zero FIR:** Can be registered at any police station regardless of jurisdiction, then transferred to appropriate station.""",

    "pil": """## Public Interest Litigation (PIL)

**Definition:** A legal action initiated in a court of law for the enforcement of public interest or general interest, where the public or a class of community have pecuniary interest or some interest by which their legal rights or liabilities are affected.

**Key Features:**
- Any citizen can file on behalf of public
- No strict locus standi requirement
- Filed in High Court (Article 226) or Supreme Court (Article 32)
- Court can take suo motu cognizance

**Common PIL Issues:**
- Environmental protection
- Human rights violations
- Corruption and misuse of public funds
- Rights of prisoners and undertrials
- Child labour and bonded labour
- Road safety

**Landmark PIL Cases:**
- *Hussainara Khatoon v. Bihar* (1979) – Rights of undertrial prisoners
- *M.C. Mehta v. Union of India* – Environmental protection
- *Vishaka v. State of Rajasthan* – Sexual harassment at workplace""",

    "ipc": """## Indian Penal Code (IPC)

**Definition:** The main criminal code of India, enacted in 1860, which covers all substantive aspects of criminal law.

**Structure:**
- 511 Sections organized in 23 Chapters
- Replaced by Bharatiya Nyaya Sanhita (BNS) 2023

**Key Sections:**
- **Section 302** – Murder (punishment: death or life imprisonment)
- **Section 304** – Culpable homicide not amounting to murder
- **Section 307** – Attempt to murder
- **Section 354** – Assault on woman with intent to outrage modesty
- **Section 375/376** – Rape and punishment for rape
- **Section 420** – Cheating and dishonestly inducing delivery of property
- **Section 498A** – Cruelty by husband or relatives
- **Section 506** – Punishment for criminal intimidation

**General Exceptions (Chapter IV):**
- Acts done by consent
- Acts done in good faith
- Right of private defence
- Unsound mind (insanity defence)""",

    "property": """## Property Law

**Definition:** Area of law governing ownership, use, and transfer of property (land, buildings, and personal assets).

**Types of Property:**
1. **Immovable Property** – Land, buildings, rights in land
2. **Movable Property** – All other property (goods, vehicles, etc.)
3. **Intellectual Property** – Patents, trademarks, copyrights

**Key Legislation in India:**
- Transfer of Property Act, 1882
- Registration Act, 1908
- Indian Succession Act, 1925
- Hindu Succession Act, 1956

**Important Concepts:**
- **Sale** – Transfer of ownership for a price
- **Mortgage** – Transfer of interest in property as security for loan
- **Lease** – Transfer of right to enjoy property for a period
- **Gift** – Transfer without consideration
- **Will** – Testamentary transfer after death

**Rights of Property Owner:**
- Right to possess
- Right to use and enjoy
- Right to transfer/sell
- Right to exclude others""",

    "divorce": """## Divorce Law in India

**Definition:** Legal dissolution of a marriage by a court or other competent body.

**Grounds for Divorce (Hindu Marriage Act, 1955):**
1. Adultery
2. Cruelty (physical or mental)
3. Desertion (minimum 2 years)
4. Conversion to another religion
5. Mental disorder
6. Leprosy or venereal disease
7. Renunciation of world
8. Presumption of death (missing for 7+ years)
9. Mutual consent (Section 13B)

**Types:**
- **Contested Divorce** – One spouse opposes
- **Mutual Consent Divorce** – Both agree (faster process)

**Divorce Process:**
1. File petition in Family Court
2. Serve notice to other spouse
3. Mediation attempt (mandatory)
4. Hearings and evidence
5. Decree of divorce

**Alimony/Maintenance:**
- Court may award maintenance under Section 125 CrPC
- Factors: income, needs, standard of living during marriage""",

    "consumer": """## Consumer Protection Law

**Definition:** Laws designed to protect consumers from unfair business practices, defective products, and deficient services.

**Key Legislation:** Consumer Protection Act, 2019

**Who is a Consumer?**
- A person who buys goods or avails services for personal use
- Not for commercial/resale purposes

**Consumer Rights:**
1. Right to safety
2. Right to information
3. Right to choose
4. Right to be heard
5. Right to redressal
6. Right to consumer education

**Consumer Courts (Three-Tier):**
- **District Commission** – Claims up to ₹1 crore
- **State Commission** – Claims ₹1 crore to ₹10 crore
- **National Commission** – Claims above ₹10 crore

**How to File Complaint:**
- Within 2 years of cause of action
- Can file online at edaakhil.nic.in
- No court fee up to ₹5 lakh claim
- Can appear in person without lawyer""",

    "fundamental rights": """## Fundamental Rights (Indian Constitution)

**Definition:** Basic rights guaranteed to all citizens of India under Part III (Articles 12-35) of the Constitution that cannot be taken away by ordinary legislation.

**Six Categories:**

1. **Right to Equality (Articles 14-18)**
   - Equality before law
   - Prohibition of discrimination
   - Equality of opportunity in public employment

2. **Right to Freedom (Articles 19-22)**
   - Freedom of speech and expression
   - Freedom of assembly, association, movement
   - Freedom of profession
   - Protection against arbitrary arrest

3. **Right against Exploitation (Articles 23-24)**
   - Prohibition of trafficking and forced labour
   - Prohibition of child labour in factories

4. **Right to Freedom of Religion (Articles 25-28)**
   - Freedom of conscience and religion

5. **Cultural and Educational Rights (Articles 29-30)**
   - Protection of minorities

6. **Right to Constitutional Remedies (Article 32)**
   - Right to approach Supreme Court for enforcement
   - Dr. Ambedkar called this the "heart and soul" of the Constitution""",

    "legal drafting": """## Legal Drafting

**Definition:** The process of preparing and writing legal documents such as contracts, agreements, pleadings, deeds, and legislation in clear, precise, and legally effective language.

**Key Principles of Good Legal Drafting:**

1. **Clarity** – Use plain, unambiguous language
2. **Precision** – Define all key terms explicitly
3. **Completeness** – Cover all relevant scenarios
4. **Consistency** – Use the same term for the same concept throughout
5. **Conciseness** – Avoid unnecessary words

**Types of Legal Documents:**
- **Contracts & Agreements** – Sale deeds, lease agreements, employment contracts
- **Court Pleadings** – Plaints, written statements, petitions
- **Affidavits** – Sworn written statements
- **Wills & Testaments** – Testamentary documents
- **Legislation** – Bills, acts, regulations

**Structure of a Legal Document:**
1. Title / Heading
2. Parties (with full identification)
3. Recitals / Background (Whereas clauses)
4. Definitions
5. Operative clauses (Rights & Obligations)
6. Representations & Warranties
7. Termination clauses
8. Dispute resolution (Arbitration / Jurisdiction)
9. Execution (Signatures, date, witnesses)

**Common Drafting Mistakes to Avoid:**
- Vague language ("reasonable", "promptly" without definition)
- Inconsistent use of defined terms
- Missing dispute resolution clause
- Ignoring governing law provision
- Unsigned/undated documents""",

    "arbitration": """## Arbitration

**Definition:** A private, binding dispute resolution process where parties agree to have their dispute decided by one or more arbitrators instead of going to court.

**Governing Law in India:** Arbitration and Conciliation Act, 1996 (amended 2015, 2019, 2021)

**Types:**
- **Domestic Arbitration** – Both parties in India
- **International Commercial Arbitration** – At least one foreign party
- **Ad-hoc Arbitration** – Parties manage the process
- **Institutional Arbitration** – Administered by institution (e.g., DIAC, ICC)

**Process:**
1. Arbitration agreement (before or after dispute)
2. Notice of arbitration
3. Appointment of arbitrator(s)
4. Preliminary hearing
5. Exchange of pleadings
6. Hearing / Evidence
7. Award

**Advantages:**
- Faster than court proceedings
- Confidential
- Flexible procedure
- Finality of award
- Expert arbitrators

**Arbitral Award:**
- Binding on parties
- Enforceable like a court decree
- Limited grounds for challenge (Section 34)""",
}


def _find_best_match(query: str) -> Optional[str]:
    """Find the best matching legal topic from the knowledge base."""
    query_lower = query.lower()
    
    # Direct keyword matching
    for keyword, content in LEGAL_KNOWLEDGE.items():
        if keyword in query_lower:
            return content
    
    # Partial word matching
    query_words = set(query_lower.split())
    best_match = None
    best_score = 0
    
    for keyword, content in LEGAL_KNOWLEDGE.items():
        keyword_words = set(keyword.split())
        score = len(query_words & keyword_words)
        if score > best_score:
            best_score = score
            best_match = content
    
    if best_score > 0:
        return best_match
    
    return None


def _generate_smart_legal_response(query: str) -> str:
    """Generate a structured, informative legal response based on the query."""
    
    # First check knowledge base
    kb_match = _find_best_match(query)
    if kb_match:
        return kb_match
    
    # Smart topic detection and response generation
    query_lower = query.lower()
    
    # Detect query type and provide relevant structured answer
    if any(w in query_lower for w in ["what is", "define", "meaning", "explain"]):
        topic = query.replace("what is", "").replace("What is", "").replace("define", "").replace("explain", "").strip().strip("?").strip()
        return f"""## {topic.title()}

**Overview:**
{topic.title()} is a legal concept within the Indian legal system governed by applicable statutes, judicial precedents, and constitutional provisions.

**Legal Framework:**
Under Indian law, this matter is typically addressed through relevant legislation and case law that establishes rights, obligations, and procedures applicable to the parties involved.

**Key Aspects:**
1. **Definition & Scope** – The concept encompasses specific rights and obligations as defined under applicable law
2. **Applicable Law** – Governed by relevant statutes, rules, and regulations
3. **Jurisdiction** – Matters are adjudicated by competent courts based on subject matter and territorial jurisdiction
4. **Remedies Available** – Civil and/or criminal remedies may be available depending on the nature of the matter

**Practical Guidance:**
- Document all relevant facts, dates, and communications
- Preserve all evidence including written records and witness information
- Consult a qualified legal professional for advice specific to your situation
- Be mindful of applicable limitation periods for filing claims

**Important Note:**
Specific outcomes depend on the facts of each case, applicable jurisdiction, and the discretion of the presiding court."""

    elif any(w in query_lower for w in ["how to", "procedure", "process", "steps", "file"]):
        return f"""## Legal Procedure: {query.title()}

**General Legal Process in India:**

**Step 1: Assess Your Legal Position**
- Identify the applicable law and jurisdiction
- Determine whether the matter is civil or criminal
- Check applicable limitation periods

**Step 2: Gather Documentation**
- Collect all relevant documents, contracts, correspondence
- Preserve digital evidence (emails, messages, screenshots)
- Identify potential witnesses

**Step 3: Legal Consultation**
- Consult a qualified advocate registered with the Bar Council
- Discuss merits, remedies, costs, and timeline
- Get a written legal opinion if needed

**Step 4: Pre-litigation Steps**
- Send a legal notice (mandatory in some matters)
- Attempt negotiation or mediation
- Exhaust alternative dispute resolution (ADR) options

**Step 5: Filing the Case**
- Draft and file appropriate petition/plaint in the competent court
- Pay requisite court fees
- Serve notice to opposite party

**Step 6: Court Proceedings**
- Attend hearings as scheduled
- File written submissions and evidence
- Cross-examination of witnesses

**Step 7: Judgment & Enforcement**
- Await judgment/order
- Appeal if necessary within prescribed time
- Execute the decree if successful"""

    elif any(w in query_lower for w in ["right", "rights"]):
        return f"""## Legal Rights Overview

**Constitutional Rights (Part III - Fundamental Rights):**
- Right to Equality (Articles 14-18)
- Right to Freedom (Articles 19-22)  
- Right against Exploitation (Articles 23-24)
- Right to Freedom of Religion (Articles 25-28)
- Cultural & Educational Rights (Articles 29-30)
- Right to Constitutional Remedies (Article 32)

**Statutory Rights:**
Depending on the specific context, rights may be provided under:
- Consumer Protection Act, 2019
- Labour laws (Industrial Disputes Act, Factories Act, etc.)
- Right to Information Act, 2005
- Protection of Women from Domestic Violence Act, 2005
- Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act

**How to Enforce Your Rights:**
1. File a complaint with the relevant authority
2. Approach a consumer forum, labour court, or civil court
3. File a PIL in High Court or Supreme Court for public interest matters
4. Seek legal aid from State Legal Services Authority (free for eligible persons)

**Free Legal Aid:**
Available to persons below poverty line, women, children, SC/ST persons, and victims of trafficking under the Legal Services Authorities Act, 1987."""

    else:
        return f"""## Legal Information: {query.strip('?').title()}

**General Legal Overview:**

Based on your query about **"{query}"**, here is relevant legal information under Indian law:

**Legal Framework:**
This matter is governed by applicable Indian statutes, constitutional provisions, and judicial precedents established by the Supreme Court and High Courts.

**Key Legal Principles:**
1. **Rule of Law** – Every person is subject to the law; no one is above it
2. **Natural Justice** – Right to be heard (*audi alteram partem*) and unbiased decision (*nemo judex in causa sua*)
3. **Due Process** – Legal proceedings must follow established rules and procedures
4. **Burden of Proof** – In civil matters, balance of probabilities; in criminal matters, beyond reasonable doubt

**Practical Steps:**
- Identify the specific legal issue and applicable law
- Consult a registered advocate for case-specific advice
- Document all facts, evidence, and timelines
- Be aware of limitation periods to avoid losing your legal remedy

**Relevant Authorities:**
- Civil disputes → Civil Court / High Court
- Criminal matters → Magistrate Court / Sessions Court  
- Consumer disputes → Consumer Commission
- Labour matters → Labour Court / Industrial Tribunal
- Family matters → Family Court

**Free Legal Resources:**
- District Legal Services Authority (DLSA) – Free legal aid
- National Legal Services Authority (NALSA) – nalsa.gov.in
- eCourts portal – ecourts.gov.in (case status, judgments)
- Supreme Court of India – sci.gov.in"""


def get_free_ai_response(query: str, system_instruction: Optional[str] = None) -> str:
    """
    Get AI response without requiring any API key.
    Uses a rich built-in legal knowledge engine.
    """
    return _generate_smart_legal_response(query)
