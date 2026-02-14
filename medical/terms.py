"""
Medical terminology lists for STT phrase boosting.

Each list contains (term, boost_value) tuples.
Boost values: 10 = moderate boost, 20 = strong boost.

Users can add custom terms by editing this file.
"""

PATHOLOGY_TERMS_KO = [
    ("심근경색", 20), ("뇌경색", 20), ("폐색전증", 20),
    ("동맥경화", 20), ("혈전", 15), ("색전", 15),
    ("경색", 15), ("괴사", 15), ("허혈", 15),
    ("염증", 15), ("부종", 15), ("충혈", 15),
    ("출혈", 15), ("혈종", 15), ("삼출", 15),
    ("삼출액", 15), ("농양", 15), ("육아종", 15),
    ("섬유화", 15), ("화생", 15), ("이형성", 15),
    ("신생물", 15), ("양성종양", 15), ("악성종양", 20),
    ("전이", 20), ("침윤", 15), ("분화", 15),
    ("위축", 15), ("비대", 15), ("증식", 15),
    ("과형성", 15), ("아포토시스", 15), ("세포사멸", 15),
    ("응고괴사", 15), ("액화괴사", 15), ("건락괴사", 15),
    ("지방괴사", 15), ("섬유소양괴사", 15),
    ("혈관신생", 15), ("반흔", 10), ("켈로이드", 10),
    ("혈관염", 15), ("죽상경화증", 20), ("대동맥류", 15),
    ("심낭염", 15), ("심근염", 15), ("심내막염", 15),
    ("판막질환", 15), ("암종", 20), ("육종", 20),
    ("림프종", 20), ("백혈병", 20), ("골수종", 15),
]

PATHOLOGY_TERMS_EN = [
    ("myocardial infarction", 20), ("cerebral infarction", 20),
    ("pulmonary embolism", 20), ("atherosclerosis", 20),
    ("thrombosis", 15), ("embolism", 15), ("infarction", 15),
    ("necrosis", 15), ("ischemia", 15), ("inflammation", 15),
    ("edema", 15), ("hyperemia", 15), ("hemorrhage", 15),
    ("hematoma", 15), ("exudate", 15), ("abscess", 15),
    ("granuloma", 15), ("fibrosis", 15), ("metaplasia", 15),
    ("dysplasia", 15), ("neoplasm", 15), ("benign tumor", 15),
    ("malignant tumor", 20), ("metastasis", 20), ("invasion", 15),
    ("differentiation", 15), ("atrophy", 15), ("hypertrophy", 15),
    ("hyperplasia", 15), ("apoptosis", 15),
    ("coagulative necrosis", 15), ("liquefactive necrosis", 15),
    ("caseous necrosis", 15), ("fat necrosis", 15),
    ("fibrinoid necrosis", 15), ("angiogenesis", 15),
    ("carcinoma", 20), ("sarcoma", 20), ("lymphoma", 20),
    ("leukemia", 20), ("myeloma", 15),
    ("TNM staging", 15), ("grading", 10),
]

PHYSIOLOGY_TERMS_KO = [
    ("활동전위", 20), ("안정막전위", 15), ("탈분극", 20),
    ("재분극", 15), ("과분극", 15), ("역치", 15),
    ("불응기", 15), ("시냅스", 15), ("신경전달물질", 15),
    ("아세틸콜린", 20), ("노르에피네프린", 20),
    ("교감신경", 15), ("부교감신경", 15), ("자율신경계", 15),
    ("심박출량", 20), ("일회박출량", 15), ("심박수", 15),
    ("전부하", 15), ("후부하", 15), ("수축력", 15),
    ("혈압", 15), ("말초저항", 15),
    ("환기", 15), ("관류", 15), ("가스교환", 15),
    ("산소해리곡선", 20), ("폐활량", 15), ("잔기량", 15),
    ("기능적잔기용량", 15), ("사강", 15),
    ("사구체여과율", 20), ("크레아티닌", 15),
    ("레닌", 15), ("안지오텐신", 20), ("알도스테론", 20),
    ("항이뇨호르몬", 15), ("나트륨재흡수", 15),
    ("삼투압", 15), ("산염기균형", 15),
    ("대사성산증", 15), ("호흡성산증", 15),
    ("대사성알칼리증", 15), ("호흡성알칼리증", 15),
    ("내분비", 15), ("호르몬", 15), ("음성되먹임", 15),
    ("양성되먹임", 15), ("수용체", 15),
]

PHYSIOLOGY_TERMS_EN = [
    ("action potential", 20), ("resting membrane potential", 15),
    ("depolarization", 20), ("repolarization", 15),
    ("hyperpolarization", 15), ("threshold", 15),
    ("refractory period", 15), ("synapse", 15),
    ("neurotransmitter", 15), ("acetylcholine", 20),
    ("norepinephrine", 20), ("sympathetic", 15),
    ("parasympathetic", 15), ("autonomic nervous system", 15),
    ("cardiac output", 20), ("stroke volume", 15),
    ("heart rate", 15), ("preload", 15), ("afterload", 15),
    ("contractility", 15), ("blood pressure", 15),
    ("peripheral resistance", 15),
    ("ventilation", 15), ("perfusion", 15), ("gas exchange", 15),
    ("oxygen dissociation curve", 20), ("vital capacity", 15),
    ("residual volume", 15), ("functional residual capacity", 15),
    ("dead space", 15),
    ("glomerular filtration rate", 20), ("GFR", 20),
    ("creatinine", 15), ("renin", 15),
    ("angiotensin", 20), ("aldosterone", 20),
    ("antidiuretic hormone", 15), ("ADH", 15),
    ("osmolality", 15), ("acid-base balance", 15),
    ("metabolic acidosis", 15), ("respiratory acidosis", 15),
    ("metabolic alkalosis", 15), ("respiratory alkalosis", 15),
    ("endocrine", 15), ("negative feedback", 15),
    ("Frank-Starling", 15), ("Starling forces", 15),
]

PHARMACOLOGY_TERMS_KO = [
    ("약동학", 20), ("약력학", 20),
    ("흡수", 15), ("분포", 15), ("대사", 15), ("배설", 15),
    ("생체이용률", 15), ("반감기", 20), ("정상상태", 15),
    ("치료역", 15), ("최소유효농도", 15), ("최소독성농도", 15),
    ("용량반응곡선", 15), ("효능", 15), ("역가", 15),
    ("작용제", 15), ("길항제", 15), ("부분작용제", 15),
    ("경쟁적길항", 15), ("비경쟁적길항", 15),
    ("수용체", 15), ("리간드", 15),
    ("부작용", 15), ("이상반응", 15), ("약물상호작용", 15),
    ("효소유도", 15), ("효소억제", 15),
    ("시토크롬", 15), ("일차통과효과", 15),
    ("베타차단제", 20), ("칼슘채널차단제", 20),
    ("안지오텐신전환효소억제제", 20), ("이뇨제", 20),
    ("항생제", 20), ("항응고제", 20), ("항혈소판제", 20),
    ("스타틴", 20), ("프로톤펌프억제제", 15),
    ("벤조디아제핀", 15), ("아편유사제", 15),
    ("비스테로이드성항염증제", 15), ("스테로이드", 15),
    ("항히스타민제", 15), ("기관지확장제", 15),
    ("인슐린", 20), ("메트포르민", 20),
    ("와파린", 20), ("헤파린", 20), ("아스피린", 20),
]

PHARMACOLOGY_TERMS_EN = [
    ("pharmacokinetics", 20), ("pharmacodynamics", 20),
    ("absorption", 15), ("distribution", 15),
    ("metabolism", 15), ("excretion", 15),
    ("bioavailability", 15), ("half-life", 20),
    ("steady state", 15), ("therapeutic window", 15),
    ("dose-response curve", 15), ("efficacy", 15), ("potency", 15),
    ("agonist", 15), ("antagonist", 15), ("partial agonist", 15),
    ("competitive antagonism", 15), ("noncompetitive antagonism", 15),
    ("receptor", 15), ("ligand", 15),
    ("adverse effect", 15), ("drug interaction", 15),
    ("enzyme induction", 15), ("enzyme inhibition", 15),
    ("cytochrome P450", 20), ("CYP3A4", 15), ("CYP2D6", 15),
    ("first-pass effect", 15),
    ("beta blocker", 20), ("calcium channel blocker", 20),
    ("ACE inhibitor", 20), ("ARB", 15), ("diuretic", 20),
    ("antibiotic", 20), ("anticoagulant", 20),
    ("antiplatelet", 20), ("statin", 20), ("PPI", 15),
    ("benzodiazepine", 15), ("opioid", 15), ("NSAID", 20),
    ("corticosteroid", 15), ("antihistamine", 15),
    ("bronchodilator", 15), ("insulin", 20), ("metformin", 20),
    ("warfarin", 20), ("heparin", 20), ("aspirin", 20),
    ("loading dose", 15), ("maintenance dose", 15),
    ("volume of distribution", 15), ("clearance", 15),
]

IMMUNOLOGY_TERMS_KO = [
    ("면역글로불린", 20), ("항체", 20), ("항원", 20),
    ("면역반응", 15), ("선천면역", 15), ("적응면역", 15),
    ("체액성면역", 15), ("세포성면역", 15),
    ("티세포", 20), ("비세포", 20), ("대식세포", 15),
    ("수지상세포", 15), ("자연살해세포", 15),
    ("보체", 15), ("보체계", 15),
    ("사이토카인", 20), ("인터루킨", 15), ("인터페론", 15),
    ("종양괴사인자", 15), ("히스타민", 15),
    ("주조직적합복합체", 20), ("에이치엘에이", 15),
    ("자가면역", 20), ("과민반응", 20),
    ("제1형과민반응", 15), ("제2형과민반응", 15),
    ("제3형과민반응", 15), ("제4형과민반응", 15),
    ("아나필락시스", 20), ("이식거부반응", 15),
    ("면역결핍", 15), ("면역억제제", 15),
    ("백신", 15), ("능동면역", 15), ("수동면역", 15),
    ("톨유사수용체", 15), ("항원제시세포", 15),
    ("클론선택", 15), ("면역관용", 15),
]

IMMUNOLOGY_TERMS_EN = [
    ("immunoglobulin", 20), ("antibody", 20), ("antigen", 20),
    ("immune response", 15), ("innate immunity", 15),
    ("adaptive immunity", 15), ("humoral immunity", 15),
    ("cell-mediated immunity", 15),
    ("T cell", 20), ("B cell", 20), ("macrophage", 15),
    ("dendritic cell", 15), ("natural killer cell", 15),
    ("complement", 15), ("complement system", 15),
    ("cytokine", 20), ("interleukin", 15), ("interferon", 15),
    ("tumor necrosis factor", 15), ("TNF", 15),
    ("histamine", 15),
    ("major histocompatibility complex", 20), ("MHC", 20),
    ("HLA", 20), ("autoimmune", 20),
    ("hypersensitivity", 20), ("type I hypersensitivity", 15),
    ("type II hypersensitivity", 15), ("type III hypersensitivity", 15),
    ("type IV hypersensitivity", 15), ("anaphylaxis", 20),
    ("graft rejection", 15), ("immunodeficiency", 15),
    ("immunosuppressant", 15), ("vaccine", 15),
    ("active immunity", 15), ("passive immunity", 15),
    ("toll-like receptor", 15), ("TLR", 15),
    ("antigen-presenting cell", 15), ("APC", 15),
    ("clonal selection", 15), ("immune tolerance", 15),
    ("IgG", 15), ("IgA", 15), ("IgM", 15), ("IgE", 15),
    ("opsonization", 15), ("phagocytosis", 15),
]

BIOCHEMISTRY_TERMS_KO = [
    ("미토콘드리아", 20), ("소포체", 15), ("골지체", 15),
    ("리보솜", 15), ("리소좀", 15),
    ("해당과정", 20), ("시트르산회로", 20), ("전자전달계", 20),
    ("산화적인산화", 20), ("기질수준인산화", 15),
    ("포도당신생합성", 15), ("글리코겐합성", 15),
    ("글리코겐분해", 15), ("지방산합성", 15),
    ("베타산화", 20), ("케톤체", 15),
    ("아미노산대사", 15), ("요소회로", 15),
    ("전사", 15), ("번역", 15), ("복제", 15),
    ("디엔에이", 15), ("알엔에이", 15),
    ("효소", 15), ("기질", 15), ("보조인자", 15),
    ("미카엘리스멘텐", 15), ("경쟁적억제", 15),
    ("비경쟁적억제", 15), ("알로스테릭", 15),
    ("비타민", 15), ("조효소", 15),
    ("에이티피", 20), ("엔에이디에이치", 15),
    ("에프에이디에이치투", 15),
    ("콜레스테롤", 15), ("중성지방", 15),
    ("인지질", 15), ("당단백질", 15),
    ("헤모글로빈", 20), ("미오글로빈", 15),
]

BIOCHEMISTRY_TERMS_EN = [
    ("mitochondria", 20), ("endoplasmic reticulum", 15),
    ("Golgi apparatus", 15), ("ribosome", 15), ("lysosome", 15),
    ("glycolysis", 20), ("citric acid cycle", 20), ("TCA cycle", 20),
    ("Krebs cycle", 20), ("electron transport chain", 20),
    ("oxidative phosphorylation", 20),
    ("substrate-level phosphorylation", 15),
    ("gluconeogenesis", 15), ("glycogenesis", 15),
    ("glycogenolysis", 15), ("lipogenesis", 15),
    ("beta oxidation", 20), ("ketone bodies", 15),
    ("amino acid metabolism", 15), ("urea cycle", 15),
    ("transcription", 15), ("translation", 15), ("replication", 15),
    ("DNA", 15), ("RNA", 15), ("mRNA", 15), ("tRNA", 15),
    ("enzyme", 15), ("substrate", 15), ("cofactor", 15),
    ("Michaelis-Menten", 15), ("Km", 10), ("Vmax", 10),
    ("competitive inhibition", 15), ("noncompetitive inhibition", 15),
    ("allosteric", 15), ("vitamin", 15), ("coenzyme", 15),
    ("ATP", 20), ("NADH", 15), ("FADH2", 15),
    ("cholesterol", 15), ("triglyceride", 15),
    ("phospholipid", 15), ("glycoprotein", 15),
    ("hemoglobin", 20), ("myoglobin", 15),
    ("Western blot", 10), ("PCR", 15), ("ELISA", 15),
]

CLINICAL_TERMS_KO = [
    ("고혈압", 20), ("당뇨병", 20), ("심부전", 20),
    ("관상동맥질환", 20), ("협심증", 20),
    ("부정맥", 20), ("심방세동", 20), ("심실세동", 20),
    ("뇌졸중", 20), ("일과성허혈발작", 15),
    ("폐렴", 20), ("천식", 20), ("만성폐쇄성폐질환", 20),
    ("결핵", 20), ("간경변", 15), ("간염", 15),
    ("췌장염", 15), ("위궤양", 15), ("크론병", 15),
    ("궤양성대장염", 15),
    ("급성신손상", 15), ("만성콩팥병", 15), ("신증후군", 15),
    ("사구체신염", 15),
    ("갑상선기능항진증", 15), ("갑상선기능저하증", 15),
    ("쿠싱증후군", 15), ("에디슨병", 15),
    ("빈혈", 15), ("철결핍성빈혈", 15),
    ("재생불량성빈혈", 15), ("용혈성빈혈", 15),
    ("파종성혈관내응고", 15), ("혈소판감소증", 15),
    ("패혈증", 20), ("쇼크", 20), ("심정지", 20),
    ("전해질이상", 15), ("저나트륨혈증", 15), ("고칼륨혈증", 15),
    ("류마티스관절염", 15), ("전신홍반루푸스", 15),
    ("골다공증", 20), ("통풍", 10),
]

BONE_TERMS_KO = [
    ("골표지자", 20), ("골밀도", 20), ("골흡수", 20),
    ("골형성", 20), ("골교체", 15), ("골대사", 20),
    ("골감소증", 15), ("골연화증", 15),
    ("파골세포", 20), ("조골세포", 20), ("골세포", 15),
    ("골흡수표지자", 20), ("골형성표지자", 20),
    ("부갑상선호르몬", 20), ("부갑상선", 15),
    ("칼시토닌", 15), ("비타민디", 20),
    ("칼슘", 15), ("인", 10), ("마그네슘", 10),
    ("알칼리인산분해효소", 15), ("오스테오칼신", 20),
    ("골절", 20), ("척추골절", 15), ("대퇴골절", 15),
    ("압박골절", 15), ("취약골절", 15),
    ("이중에너지엑스선흡수법", 15),
    ("비스포스포네이트", 20), ("데노수맙", 20),
    ("테리파라타이드", 20), ("로모소주맙", 15),
    ("라록시펜", 15), ("바제독시펜", 15),
    ("갱년기", 10), ("폐경", 15), ("폐경후", 15),
    ("스테로이드유발골다공증", 15),
    ("골절위험도", 15), ("골질", 15),
    ("해면골", 10), ("피질골", 10),
    ("교원질", 10), ("콜라겐", 15),
]

BONE_TERMS_EN = [
    ("bone turnover marker", 20), ("bone marker", 20),
    ("bone mineral density", 20), ("BMD", 20),
    ("bone resorption", 20), ("bone formation", 20),
    ("bone turnover", 20), ("bone metabolism", 20),
    ("osteoclast", 20), ("osteoblast", 20), ("osteocyte", 15),
    ("osteoporosis", 20), ("osteopenia", 15), ("osteomalacia", 15),
    ("CTX", 20), ("C-terminal telopeptide", 20),
    ("NTX", 15), ("N-terminal telopeptide", 15),
    ("P1NP", 20), ("procollagen", 15),
    ("osteocalcin", 20), ("alkaline phosphatase", 15), ("ALP", 15),
    ("bone-specific ALP", 15), ("BSALP", 15),
    ("TRAP-5b", 15), ("deoxypyridinoline", 15), ("DPD", 15),
    ("parathyroid hormone", 20), ("PTH", 20),
    ("calcitonin", 15), ("vitamin D", 20),
    ("calcitriol", 15), ("calcidiol", 15),
    ("25-hydroxyvitamin D", 15), ("1,25-dihydroxyvitamin D", 15),
    ("calcium", 15), ("phosphorus", 10),
    ("DEXA", 20), ("DXA", 20), ("T-score", 20), ("Z-score", 15),
    ("FRAX", 20), ("fracture risk", 15),
    ("fracture", 20), ("vertebral fracture", 15),
    ("hip fracture", 15), ("fragility fracture", 15),
    ("bisphosphonate", 20), ("alendronate", 15),
    ("risedronate", 15), ("zoledronic acid", 15),
    ("ibandronate", 15), ("denosumab", 20),
    ("teriparatide", 20), ("abaloparatide", 15),
    ("romosozumab", 15), ("raloxifene", 15),
    ("SERM", 15), ("RANKL", 20), ("OPG", 15),
    ("osteoprotegerin", 15), ("sclerostin", 15),
    ("bone remodeling", 15), ("peak bone mass", 15),
    ("collagen", 15), ("crosslink", 15),
    ("trabecular bone", 10), ("cortical bone", 10),
    ("drug holiday", 10), ("treatment gap", 10),
    ("postmenopausal osteoporosis", 15),
    ("glucocorticoid-induced osteoporosis", 15),
]

CLINICAL_TERMS_EN = [
    ("hypertension", 20), ("diabetes mellitus", 20),
    ("heart failure", 20), ("coronary artery disease", 20),
    ("angina pectoris", 20), ("arrhythmia", 20),
    ("atrial fibrillation", 20), ("ventricular fibrillation", 20),
    ("stroke", 20), ("transient ischemic attack", 15), ("TIA", 15),
    ("pneumonia", 20), ("asthma", 20), ("COPD", 20),
    ("tuberculosis", 20), ("cirrhosis", 15), ("hepatitis", 15),
    ("pancreatitis", 15), ("peptic ulcer", 15),
    ("Crohn's disease", 15), ("ulcerative colitis", 15),
    ("acute kidney injury", 15), ("AKI", 15),
    ("chronic kidney disease", 15), ("CKD", 15),
    ("nephrotic syndrome", 15), ("glomerulonephritis", 15),
    ("hyperthyroidism", 15), ("hypothyroidism", 15),
    ("Cushing syndrome", 15), ("Addison disease", 15),
    ("anemia", 15), ("iron deficiency anemia", 15),
    ("aplastic anemia", 15), ("hemolytic anemia", 15),
    ("DIC", 15), ("disseminated intravascular coagulation", 15),
    ("thrombocytopenia", 15),
    ("sepsis", 20), ("shock", 20), ("cardiac arrest", 20),
    ("electrolyte imbalance", 15), ("hyponatremia", 15),
    ("hyperkalemia", 15),
    ("rheumatoid arthritis", 15), ("systemic lupus erythematosus", 15),
    ("SLE", 15), ("osteoporosis", 20), ("gout", 10),
    ("ECG", 15), ("EKG", 15), ("chest X-ray", 10),
    ("CT scan", 10), ("MRI", 10), ("ultrasound", 10),
]


import threading

_dynamic_terms: list[tuple[str, int]] = []
_lock = threading.Lock()


def add_dynamic_terms(terms: list[str], boost: int = 15):
    """Add terms discovered from screen content at runtime. Thread-safe."""
    with _lock:
        existing = {t for t, _ in _dynamic_terms}
        for term in terms:
            term = term.strip()
            if term and len(term) >= 2 and term not in existing:
                _dynamic_terms.append((term, boost))
                existing.add(term)


def get_dynamic_terms() -> list[tuple[str, int]]:
    """Return dynamically added terms. Thread-safe."""
    with _lock:
        return list(_dynamic_terms)


def get_all_medical_terms() -> list[tuple[str, int]]:
    """Return all medical terms (static + dynamic) with their boost values."""
    all_terms = []
    for var_name, var_val in globals().items():
        if var_name.endswith(("_TERMS_KO", "_TERMS_EN")):
            all_terms.extend(var_val)
    with _lock:
        all_terms.extend(_dynamic_terms)
    return all_terms


def format_for_deepgram() -> list[str]:
    """Return all terms formatted for Deepgram keyword boosting.

    Deepgram keywords format: 'term:intensity' where intensity is -10 to 10.
    We convert from our 10-20 scale to Deepgram's 1-3 scale.

    IMPORTANT: Short ASCII abbreviations (< 4 chars like GFR, AKI, PPI, Km)
    are excluded because Deepgram aggressively hallucinates them into Korean
    speech. Only longer terms and Korean terms are boosted.
    """
    all_terms = get_all_medical_terms()
    result = []
    seen = set()
    for term, boost in all_terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        if term.isascii() and len(term) <= 4:
            continue
        dg_boost = max(1, min(3, (boost - 5) // 5))
        result.append(f"{term}:{dg_boost}")
    return result


MIXED_LECTURE_TERMS = [
    ("receptor", 15), ("ligand", 15), ("pathway", 10),
    ("signaling", 10), ("cascade", 10), ("mechanism", 10),
    ("syndrome", 10), ("disease", 10), ("disorder", 10),
    ("acute", 10), ("chronic", 10), ("benign", 10),
    ("malignant", 10), ("prognosis", 10), ("diagnosis", 10),
    ("differential diagnosis", 15), ("treatment", 10),
    ("prophylaxis", 10), ("complication", 10),
    ("sign", 10), ("symptom", 10), ("finding", 10),
    ("imaging", 10), ("biopsy", 10), ("lab", 10),
    ("CBC", 10), ("BMP", 10), ("LFT", 10),
    ("sensitivity", 10), ("specificity", 10),
    ("positive predictive value", 10), ("PPV", 10),
    ("gold standard", 10), ("first-line", 10),
]
