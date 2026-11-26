// Today's fleet in English, Hindi and Marathi. The verdict and reasons come from the API in English with a `code` and
// `args` (aerofleet/assurance/readiness.py); this file only changes how they are worded. Log warnings and setting names
// stay in English, as the autopilot writes them.
//
// REVIEWED: set to true only after a native speaker of each language has read every line below. Until then the screen
// says the translation is unchecked.
export const REVIEWED: Record<Lang, boolean> = { en: true, hi: false, mr: false }

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
  settings_never: 'Settings never checked: upload its parameter file or a flight log.',
  critical_changed: 'Safety-critical setting changed and not approved: {names}.',
  limit_changed: 'Flight-limit setting changed and not approved: {names}.',
  failsafe_off: 'Failsafe switched off: {title} ({name}).',
  critical_in_flight: '{n} safety-critical setting(s) were changed during the last flight.',
  deviated: 'The last flight left its planned route.',
  warning: 'Last flight: {warning}.',
  more_warnings: 'Last flight: {n} more warnings in its timeline.',
  allClear: "Settings match the approved configuration, the UIN is verified and the last flight's log shows no warnings.",
  noUin: 'no UIN', lastFlight: 'Last flight', min: 'min', settingsLine: 'Settings', notChecked: 'not checked',
  OK: 'ok', REVIEW: 'review', BLOCK: 'block', NO_REFERENCE: 'nothing to compare with',
  vsBaseline: 'vs approved baseline', vsPrevious: 'vs previous upload',
  model: 'Learned model (context)', vibration: 'Vibration (context)',
  vibOwn: 'above {x} of its {y} earlier flights', vibPublic: '; above {p}% of public flights', fewFlights: 'too few flights',
  empty: 'No drones in this fleet yet: upload a parameter file or a flight log on Fleet Assurance.',
  rulesTitle: 'Rules.',
  rules: 'Do not fly: an unapproved safety-critical setting change, or no UIN on record. Check first: a flight-limit change, a failsafe switched off, an unverified UIN, settings never checked, or warnings in the last flight\'s log. Ready: none of these.',
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
  settings_never: 'सेटिंग्स कभी जाँची नहीं गईं: इसकी पैरामीटर फ़ाइल या उड़ान लॉग अपलोड करें।',
  critical_changed: 'सुरक्षा से जुड़ी सेटिंग बदली गई है और उसे मंज़ूरी नहीं मिली: {names}।',
  limit_changed: 'उड़ान-सीमा की सेटिंग बदली गई है और उसे मंज़ूरी नहीं मिली: {names}।',
  failsafe_off: 'फ़ेलसेफ़ बंद है: {title} ({name})।',
  critical_in_flight: 'पिछली उड़ान के दौरान सुरक्षा से जुड़ी {n} सेटिंग बदली गईं।',
  deviated: 'पिछली उड़ान अपने तय रास्ते से हट गई।',
  warning: 'पिछली उड़ान की चेतावनी (लॉग से, अंग्रेज़ी में): {warning}',
  more_warnings: 'पिछली उड़ान: लॉग में {n} और चेतावनियाँ हैं।',
  allClear: 'सेटिंग्स मंज़ूर की गई कॉन्फ़िगरेशन से मेल खाती हैं, UIN सत्यापित है और पिछली उड़ान के लॉग में कोई चेतावनी नहीं है।',
  noUin: 'UIN नहीं', lastFlight: 'पिछली उड़ान', min: 'मिनट', settingsLine: 'सेटिंग्स', notChecked: 'जाँची नहीं गईं',
  OK: 'ठीक', REVIEW: 'जाँच ज़रूरी', BLOCK: 'रोकें', NO_REFERENCE: 'तुलना के लिए कुछ नहीं',
  vsBaseline: 'मंज़ूर बेसलाइन से तुलना', vsPrevious: 'पिछले अपलोड से तुलना',
  model: 'सीखा हुआ मॉडल (सिर्फ़ जानकारी)', vibration: 'कंपन (सिर्फ़ जानकारी)',
  vibOwn: 'अपनी पिछली {y} उड़ानों में से {x} से ज़्यादा', vibPublic: '; सार्वजनिक उड़ानों के {p}% से ज़्यादा', fewFlights: 'उड़ानें बहुत कम हैं',
  empty: 'इस बेड़े में अभी कोई ड्रोन नहीं है: Fleet Assurance पर पैरामीटर फ़ाइल या उड़ान लॉग अपलोड करें।',
  rulesTitle: 'नियम।',
  rules: 'न उड़ाएँ: सुरक्षा से जुड़ी सेटिंग में बिना मंज़ूरी का बदलाव, या कोई UIN दर्ज नहीं। पहले जाँचें: उड़ान-सीमा की सेटिंग में बदलाव, बंद फ़ेलसेफ़, UIN सत्यापित नहीं, सेटिंग्स कभी जाँची नहीं गईं, या पिछली उड़ान के लॉग में चेतावनियाँ। तैयार: इनमें से कुछ भी नहीं।',
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
  settings_never: 'सेटिंग्ज कधीच तपासल्या नाहीत: याची पॅरामीटर फाइल किंवा उड्डाण लॉग अपलोड करा.',
  critical_changed: 'सुरक्षेशी संबंधित सेटिंग बदलली आहे आणि तिला मंजुरी नाही: {names}.',
  limit_changed: 'उड्डाण-मर्यादेची सेटिंग बदलली आहे आणि तिला मंजुरी नाही: {names}.',
  failsafe_off: 'फेलसेफ बंद आहे: {title} ({name}).',
  critical_in_flight: 'मागील उड्डाणादरम्यान सुरक्षेशी संबंधित {n} सेटिंग्ज बदलल्या गेल्या.',
  deviated: 'मागील उड्डाण ठरलेल्या मार्गावरून बाजूला गेले.',
  warning: 'मागील उड्डाणाचा इशारा (लॉगमधून, इंग्रजीत): {warning}',
  more_warnings: 'मागील उड्डाण: लॉगमध्ये आणखी {n} इशारे आहेत.',
  allClear: 'सेटिंग्ज मंजूर कॉन्फिगरेशनशी जुळतात, UIN पडताळलेला आहे आणि मागील उड्डाणाच्या लॉगमध्ये कोणताही इशारा नाही.',
  noUin: 'UIN नाही', lastFlight: 'मागील उड्डाण', min: 'मिनिटे', settingsLine: 'सेटिंग्ज', notChecked: 'तपासल्या नाहीत',
  OK: 'ठीक', REVIEW: 'तपासणी आवश्यक', BLOCK: 'थांबवा', NO_REFERENCE: 'तुलनेसाठी काही नाही',
  vsBaseline: 'मंजूर बेसलाइनशी तुलना', vsPrevious: 'मागील अपलोडशी तुलना',
  model: 'शिकलेले मॉडेल (फक्त माहिती)', vibration: 'कंपन (फक्त माहिती)',
  vibOwn: 'आपल्या मागील {y} उड्डाणांपैकी {x} पेक्षा जास्त', vibPublic: '; सार्वजनिक उड्डाणांच्या {p}% पेक्षा जास्त', fewFlights: 'खूप कमी उड्डाणे',
  empty: 'या ताफ्यात अजून कोणताही ड्रोन नाही: Fleet Assurance वर पॅरामीटर फाइल किंवा उड्डाण लॉग अपलोड करा.',
  rulesTitle: 'नियम.',
  rules: 'उडवू नका: सुरक्षेशी संबंधित सेटिंगमध्ये मंजुरीशिवाय बदल, किंवा UIN नोंदलेला नाही. आधी तपासा: उड्डाण-मर्यादेच्या सेटिंगमध्ये बदल, बंद फेलसेफ, UIN पडताळलेला नाही, सेटिंग्ज कधीच तपासल्या नाहीत, किंवा मागील उड्डाणाच्या लॉगमध्ये इशारे. तयार: यापैकी काहीही नाही.',
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
