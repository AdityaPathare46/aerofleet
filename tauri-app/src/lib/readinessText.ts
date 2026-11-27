// Today's fleet in English, Hindi and Marathi. The verdict and reasons come from the API in English with a `code` and
// `args` (aerofleet/assurance/readiness.py); this file only changes how they are worded. Log warnings and setting names
// stay in English, as the autopilot writes them.
//
// REVIEWED: native-speaker reviewed on 27 Nov 2026 (Aditya Pathare, COEP).
export const REVIEWED: Record<Lang, boolean> = { en: true, hi: true, mr: true }

export type Lang = 'en' | 'hi' | 'mr'
export const LANGS: { id: Lang; label: string }[] = [{ id: 'en', label: 'English' }, { id: 'hi', label: 'हिन्दी' }, { id: 'mr', label: 'मराठी' }]
export const LOCALE: Record<Lang, string> = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' }

type Dict = Record<string, string>
const en: Dict = {
  title: "Today's fleet",
  intro: 'Which drones can go out today, and what must someone look at first. Every verdict comes from a fixed rule or a recorded fact, with a link to the evidence.',
  fleet: 'Fleet', fleetHint: '(change it on Fleet Assurance)',
  DO_NOT_FLY: 'Do not fly', CHECK_FIRST: 'Check first', READY: 'Ready',
  again: 'Check again', checking: 'Checking…', language: 'Language',
  settings: 'Settings', flight: 'Last flight', register: 'Registration',
  no_uin: 'No UIN on record: the Drone Rules 2021 require one before the drone is operated.',
  uin_unverified: 'UIN {uin} is recorded but not yet verified on Digital Sky.',
  insurance_expired: 'Third-party insurance expired on {date} (Drone Rules 2021 Rule 44).',
  insurance_expiring: 'Third-party insurance expires in {days} day(s) ({date}).',
  rpc_expired: 'Assigned pilot RPC expired on {date} (Drone Rules 2021 Rule 34).',
  accidentDossier: '48h DGCA Accident Dossier',
  settings_never: 'Settings never checked: upload its parameter file or a flight log.',
  no_baseline: 'Settings have not been compared with an approved fleet baseline yet.',
  critical_changed: 'Safety-critical setting changed and not approved: {names}.',
  limit_changed: 'Flight-limit setting changed and not approved: {names}.',
  failsafe_off: 'Failsafe switched off: {title} ({name}).',
  grounded_incident: 'Drone grounded after a reported incident or crash: inspect and log clearance before flying.',
  partial_log: 'Last flight was read from a CSV/GPX export: autopilot health and settings could not be verified.',
  critical_in_flight: '{n} safety-critical setting(s) were changed during the last flight.',
  deviated: 'The last flight left its planned route.',
  warning: 'Last flight: {warning}.',
  more_warnings: 'Last flight: {n} more warnings in its timeline.',
  allClear: 'Checks passed: UIN verified, settings checked with no unapproved changes, no failsafes switched off, and no in-air warnings on the last reviewed flight.',
  noUin: 'no UIN', lastFlight: 'Last flight', min: 'min', settingsLine: 'Settings', notChecked: 'not checked',
  OK: 'ok', REVIEW: 'review', BLOCK: 'block', NO_REFERENCE: 'nothing to compare with',
  vsBaseline: 'vs approved baseline', vsPrevious: 'vs previous upload',
  pilotNote: 'Last flight (pilot note)',
  settingNote: 'Setting note (firmware default, not a reason)',
  model: 'Learned model (context)', vibration: 'Vibration (context)',
  vibOwn: 'above {x} of its {y} earlier flights', vibPublic: '; above {p}% of public flights', fewFlights: 'too few flights',
  empty: 'No drones in this fleet yet: upload a parameter file or a flight log on Fleet Assurance.',
  rulesTitle: 'Rules.',
  rules: 'Do not fly: an unapproved safety-critical setting change, no UIN on record, or grounded after a reported incident. Check first: a flight-limit change, settings not compared with a baseline, a failsafe or safety check switched off, an unverified UIN, settings never checked, a partial CSV/GPX log, or warnings in the air during the last flight (a sensor or GPS complaint lasting 3 s or more, an autopilot error report, or an in-flight critical battery drop). Ready: none of these.',
  vibNote: 'Context only: in the study behind AeroFleet, vibration did not warn of a crash within a drone and was not shown to beat random inspection, so it never changes the verdict.',
  unchecked: '',
}
const hi: Dict = {
  title: 'आज के ड्रोन',
  intro: 'आज कौन से ड्रोन उड़ सकते हैं, और पहले किस चीज़ की जाँच करनी है। हर फ़ैसला एक तय नियम या दर्ज तथ्य से आता है, और उसके साथ सबूत का लिंक है।',
  fleet: 'बेड़ा', fleetHint: '(Fleet Assurance पर बदलें)',
  DO_NOT_FLY: 'न उड़ाएँ', CHECK_FIRST: 'पहले जाँचें', READY: 'तैयार',
  again: 'फिर से जाँचें', checking: 'जाँच हो रही है…', language: 'भाषा',
  settings: 'सेटिंग्स', flight: 'पिछली उड़ान', register: 'पंजीकरण',
  no_uin: 'कोई UIN दर्ज नहीं है: ड्रोन नियम 2021 के अनुसार ड्रोन उड़ाने से पहले UIN ज़रूरी है।',
  uin_unverified: 'UIN {uin} दर्ज है, पर Digital Sky पर अभी सत्यापित नहीं हुआ है।',
  insurance_expired: 'थर्ड-पार्टी बीमा {date} को समाप्त हो चुका है (ड्रोन नियम 2021, नियम 44)।',
  insurance_expiring: 'थर्ड-पार्टी बीमा {days} दिन में ({date}) समाप्त हो रहा है।',
  rpc_expired: 'पायलट का RPC प्रमाणपत्र {date} को समाप्त हो चुका है (ड्रोन नियम 2021, नियम 34)।',
  accidentDossier: '48 घंटे DGCA दुर्घटना रिपोर्ट',
  settings_never: 'सेटिंग्स कभी जाँची नहीं गईं: इसकी पैरामीटर फ़ाइल या उड़ान लॉग अपलोड करें।',
  no_baseline: 'सेटिंग्स की तुलना अभी तक मंज़ूर बेड़े की बेसलाइन से नहीं हुई है।',
  critical_changed: 'सुरक्षा से जुड़ी सेटिंग बदली गई है और उसे मंज़ूरी नहीं मिली: {names}।',
  limit_changed: 'उड़ान-सीमा की सेटिंग बदली गई है और उसे मंज़ूरी नहीं मिली: {names}।',
  failsafe_off: 'फ़ेलसेफ़ बंद है: {title} ({name})।',
  grounded_incident: 'दर्ज दुर्घटना या घटना के बाद ड्रोन रोका गया है: उड़ाने से पहले जाँच कर मंज़ूरी दर्ज करें।',
  partial_log: 'पिछली उड़ान CSV/GPX फ़ाइल से पढ़ी गई है: ऑटोपायलट स्वास्थ्य और सेटिंग्स की जाँच नहीं हो सकी।',
  critical_in_flight: 'पिछली उड़ान के दौरान सुरक्षा से जुड़ी {n} सेटिंग बदली गईं।',
  deviated: 'पिछली उड़ान अपने तय रास्ते से हट गई।',
  warning: 'पिछली उड़ान की चेतावनी (लॉग से, अंग्रेज़ी में): {warning}',
  more_warnings: 'पिछली उड़ान: लॉग में {n} और चेतावनियाँ हैं।',
  allClear: 'जाँच पूरी हुई: UIN सत्यापित है, सेटिंग्स में कोई बिना मंज़ूरी का बदलाव नहीं, कोई फ़ेलसेफ़ बंद नहीं, और पिछली उड़ान में हवा में कोई चेतावनी नहीं।',
  noUin: 'UIN नहीं', lastFlight: 'पिछली उड़ान', min: 'मिनट', settingsLine: 'सेटिंग्स', notChecked: 'जाँची नहीं गईं',
  OK: 'ठीक', REVIEW: 'जाँच ज़रूरी', BLOCK: 'रोकें', NO_REFERENCE: 'तुलना के लिए कुछ नहीं',
  vsBaseline: 'मंज़ूर बेसलाइन से तुलना', vsPrevious: 'पिछले अपलोड से तुलना',
  pilotNote: 'पिछली उड़ान (पायलट के लिए नोट)',
  settingNote: 'सेटिंग नोट (फ़र्मवेयर डिफ़ॉल्ट, कारण नहीं)',
  model: 'सीखा हुआ मॉडल (सिर्फ़ जानकारी)', vibration: 'कंपन (सिर्फ़ जानकारी)',
  vibOwn: 'अपनी पिछली {y} उड़ानों में से {x} से ज़्यादा', vibPublic: '; सार्वजनिक उड़ानों के {p}% से ज़्यादा', fewFlights: 'उड़ानें बहुत कम हैं',
  empty: 'इस बेड़े में अभी कोई ड्रोन नहीं है: Fleet Assurance पर पैरामीटर फ़ाइल या उड़ान लॉग अपलोड करें।',
  rulesTitle: 'नियम।',
  rules: 'न उड़ाएँ: सुरक्षा से जुड़ी सेटिंग में बिना मंज़ूरी का बदलाव, कोई UIN दर्ज नहीं, या दुर्घटना के बाद रोका गया ड्रोन। पहले जाँचें: उड़ान-सीमा की सेटिंग में बदलाव, बेसलाइन से तुलना नहीं, बंद फ़ेलसेफ़, UIN सत्यापित नहीं, सेटिंग्स कभी जाँची नहीं गईं, आंशिक CSV/GPX लॉग, या पिछली उड़ान के दौरान हवा में चेतावनियाँ (3 सेकंड या उससे लंबी सेंसर या GPS शिकायत, ऑटोपायलट त्रुटि, या उड़ान के बीच बैटरी 10% से नीचे)। तैयार: इनमें से कुछ भी नहीं।',
  vibNote: 'कंपन सिर्फ़ जानकारी के लिए है: AeroFleet जिस अध्ययन पर आधारित है, उसमें कंपन से किसी ड्रोन की दुर्घटना की पहले से चेतावनी नहीं मिली और यह बिना क्रम की (random) जाँच से बेहतर साबित नहीं हुआ, इसलिए यह फ़ैसले को कभी नहीं बदलता।',
  unchecked: 'इस अनुवाद की जाँच अभी किसी हिन्दी भाषी ने नहीं की है।',
}
const mr: Dict = {
  title: 'आजचे ड्रोन',
  intro: 'आज कोणते ड्रोन उडू शकतात, आणि आधी कशाची तपासणी करायची. प्रत्येक निर्णय ठरलेल्या नियमावर किंवा नोंदलेल्या तथ्यावर आधारित आहे, आणि त्यासोबत पुराव्याची लिंक आहे.',
  fleet: 'ताफा', fleetHint: '(Fleet Assurance वर बदला)',
  DO_NOT_FLY: 'उडवू नका', CHECK_FIRST: 'आधी तपासा', READY: 'तयार',
  again: 'पुन्हा तपासा', checking: 'तपासत आहे…', language: 'भाषा',
  settings: 'सेटिंग्ज', flight: 'मागील उड्डाण', register: 'नोंदणी',
  no_uin: 'UIN नोंदलेला नाही: ड्रोन नियम 2021 नुसार ड्रोन उडवण्यापूर्वी UIN आवश्यक आहे.',
  uin_unverified: 'UIN {uin} नोंदलेला आहे, पण Digital Sky वर अजून पडताळलेला नाही.',
  insurance_expired: 'थर्ड-पार्टी विमा {date} रोजी संपला आहे (ड्रोन नियम 2021, नियम 44).',
  insurance_expiring: 'थर्ड-पार्टी विमा {days} दिवसांत ({date}) संपणार आहे.',
  rpc_expired: 'पायलटचे RPC प्रमाणपत्र {date} रोजी संपले आहे (ड्रोन नियम 2021, नियम 34).',
  accidentDossier: '48 तास DGCA अपघात अहवाल',
  settings_never: 'सेटिंग्ज कधीच तपासल्या नाहीत: याची पॅरामीटर फाइल किंवा उड्डाण लॉग अपलोड करा.',
  no_baseline: 'सेटिंग्जची तुलना अजून मंजूर ताफ्याच्या बेसलाइनशी झालेली नाही.',
  critical_changed: 'सुरक्षेशी संबंधित सेटिंग बदलली आहे आणि तिला मंजुरी नाही: {names}.',
  limit_changed: 'उड्डाण-मर्यादेची सेटिंग बदलली आहे आणि तिला मंजुरी नाही: {names}.',
  failsafe_off: 'फेलसेफ बंद आहे: {title} ({name}).',
  grounded_incident: 'नोंदवलेल्या अपघातानंतर किंवा घटनेनंतर ड्रोन थांबवला आहे: उडवण्यापूर्वी तपासणी करून मंजुरी नोंदवा.',
  partial_log: 'मागील उड्डाण CSV/GPX फाइलमधून वाचले आहे: ऑटोपायलट आरोग्य आणि सेटिंग्ज तपासता आल्या नाहीत.',
  critical_in_flight: 'मागील उड्डाणादरम्यान सुरक्षेशी संबंधित {n} सेटिंग्ज बदलल्या गेल्या.',
  deviated: 'मागील उड्डाण ठरलेल्या मार्गावरून बाजूला गेले.',
  warning: 'मागील उड्डाणाचा इशारा (लॉगमधून, इंग्रजीत): {warning}',
  more_warnings: 'मागील उड्डाण: लॉगमध्ये आणखी {n} इशारे आहेत.',
  allClear: 'तपासणी पूर्ण झाली: UIN पडताळलेला आहे, सेटिंग्जमध्ये मंजुरीशिवाय बदल नाही, कोणतेही फेलसेफ बंद नाही, आणि मागील उड्डाणात हवेत कोणताही इशारा नाही.',
  noUin: 'UIN नाही', lastFlight: 'मागील उड्डाण', min: 'मिनिटे', settingsLine: 'सेटिंग्ज', notChecked: 'तपासल्या नाहीत',
  OK: 'ठीक', REVIEW: 'तपासणी आवश्यक', BLOCK: 'थांबवा', NO_REFERENCE: 'तुलनेसाठी काही नाही',
  vsBaseline: 'मंजूर बेसलाइनशी तुलना', vsPrevious: 'मागील अपलोडशी तुलना',
  pilotNote: 'मागील उड्डाण (पायलटसाठी नोंद)',
  settingNote: 'सेटिंग नोंद (फर्मवेअर डीफॉल्ट, कारण नाही)',
  model: 'शिकलेले मॉडेल (फक्त माहिती)', vibration: 'कंपन (फक्त माहिती)',
  vibOwn: 'आपल्या मागील {y} उड्डाणांपैकी {x} पेक्षा जास्त', vibPublic: '; सार्वजनिक उड्डाणांच्या {p}% पेक्षा जास्त', fewFlights: 'खूप कमी उड्डाणे',
  empty: 'या ताफ्यात अजून कोणताही ड्रोन नाही: Fleet Assurance वर पॅरामीटर फाइल किंवा उड्डाण लॉग अपलोड करा.',
  rulesTitle: 'नियम.',
  rules: 'उडवू नका: सुरक्षेशी संबंधित सेटिंगमध्ये मंजुरीशिवाय बदल, UIN नोंदलेला नाही, किंवा अपघातानंतर थांबवलेला ड्रोन. आधी तपासा: उड्डाण-मर्यादेच्या सेटिंगमध्ये बदल, बेसलाइनशी तुलना नाही, बंद फेलसेफ, UIN पडताळलेला नाही, सेटिंग्ज कधीच तपासल्या नाहीत, आंशिक CSV/GPX लॉग, किंवा मागील उड्डाणात हवेत असताना इशारे (3 सेकंद किंवा जास्त सेन्सर किंवा GPS तक्रार, ऑटोपायलट त्रुटी, किंवा उड्डाणादरम्यान बॅटरी 10% खाली). तयार: यापैकी काहीही नाही.',
  vibNote: 'कंपन फक्त माहितीसाठी आहे: AeroFleet ज्या अभ्यासावर आधारित आहे, त्यात कंपनामुळे एखाद्या ड्रोनच्या अपघाताची आधी सूचना मिळाली नाही आणि ते यादृच्छिक (random) तपासणीपेक्षा चांगले असल्याचे सिद्ध झाले नाही, त्यामुळे ते निर्णय कधीही बदलत नाही.',
  unchecked: 'हा अनुवाद अजून मराठी भाषकाने तपासलेला नाही.',
}
export const TEXT: Record<Lang, Dict> = { en, hi, mr }

/** One string in the chosen language, with {name} filled from `args`. Falls back to English for an unknown key. */
export function t(lang: Lang, key: string, args: Record<string, unknown> = {}): string {
  const s = TEXT[lang][key] ?? en[key] ?? key
  return s.replace(/\{(\w+)\}/g, (_, k) => String(args[k] ?? ''))
}

export function savedLang(): Lang {
  try { const v = localStorage.getItem('aerofleet_lang'); return v === 'hi' || v === 'mr' ? v : 'en' } catch { return 'en' }
}
export function saveLang(l: Lang) { try { localStorage.setItem('aerofleet_lang', l) } catch { /* private window */ } }
