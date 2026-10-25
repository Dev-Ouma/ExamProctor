/** Candidate-facing text in English and Swahili. Keys are stable; text may change with the consent version. */

const en = {
  title: "Before you start",
  consent:
    "This quiz is proctored. With your agreement, ExamProctor takes photos from your camera and, on a computer, snapshots of your whole screen during the attempt. It also records when you leave the quiz page. It never records what you type. Your teacher and exam officers review the results. AI only raises flags for a person to check; it never fails you by itself. Data is kept in Kenya for 90 days after results are final.",
  agree: "I agree",
  camera: "Allow camera",
  screen: "Share your whole screen",
  check: "Run the checks",
  ok: "Done",
  denied: "Permission refused. Allow it in your browser settings and try again.",
  missing: "No device found.",
  unsupported: "Not available on this device.",
  waiting: "Checks passed. Unlocking your quiz…",
  ready: "All checks passed. You can start the attempt.",
  blocked: "You cannot start yet:",
  retry: "Try again",
  error: "Something went wrong. Reload the page and try again.",
  staging: "Staging: synthetic data only",
  reason_camera_denied: "Camera permission was refused.",
  reason_camera_missing: "No camera was found.",
  reason_camera_unsupported: "This device cannot use a camera here.",
  reason_screen_denied: "Screen sharing was refused.",
  reason_screen_missing: "Screen sharing failed.",
  reason_screen_unsupported: "This device cannot share its screen. Use a computer.",
  reason_screen_not_whole_display: "Share your entire screen, not a window or a tab.",
  reason_network_unavailable: "The connection to the proctoring service failed.",
};

type Strings = typeof en;

const sw: Strings = {
  title: "Kabla ya kuanza",
  consent:
    "Jaribio hili linasimamiwa. Kwa idhini yako, ExamProctor itapiga picha kupitia kamera yako na, kwenye kompyuta, picha za skrini yako yote wakati wa jaribio. Pia hurekodi unapotoka kwenye ukurasa wa jaribio. Haiandiki chochote unachokichapa. Mwalimu wako na maafisa wa mitihani hukagua matokeo. AI huibua tu alama za kukaguliwa na mtu; haikufelishi yenyewe. Data huhifadhiwa nchini Kenya kwa siku 90 baada ya matokeo kuthibitishwa.",
  agree: "Ninakubali",
  camera: "Ruhusu kamera",
  screen: "Shiriki skrini yako yote",
  check: "Fanya ukaguzi",
  ok: "Imekamilika",
  denied: "Ruhusa imekataliwa. Iruhusu kwenye mipangilio ya kivinjari kisha ujaribu tena.",
  missing: "Kifaa hakijapatikana.",
  unsupported: "Haipatikani kwenye kifaa hiki.",
  waiting: "Ukaguzi umefaulu. Tunafungua jaribio lako…",
  ready: "Ukaguzi wote umefaulu. Unaweza kuanza jaribio.",
  blocked: "Huwezi kuanza bado:",
  retry: "Jaribu tena",
  error: "Hitilafu imetokea. Pakia ukurasa upya kisha ujaribu tena.",
  staging: "Majaribio: data bandia pekee",
  reason_camera_denied: "Ruhusa ya kamera imekataliwa.",
  reason_camera_missing: "Kamera haijapatikana.",
  reason_camera_unsupported: "Kifaa hiki hakiwezi kutumia kamera hapa.",
  reason_screen_denied: "Kushiriki skrini kumekataliwa.",
  reason_screen_missing: "Kushiriki skrini kumeshindwa.",
  reason_screen_unsupported: "Kifaa hiki hakiwezi kushiriki skrini. Tumia kompyuta.",
  reason_screen_not_whole_display: "Shiriki skrini nzima, si dirisha au kichupo.",
  reason_network_unavailable: "Muunganisho na huduma ya usimamizi umeshindwa.",
};

export type StringKey = keyof Strings;

export function strings(lang: string): Strings {
  return lang.toLowerCase().startsWith("sw") ? sw : en;
}
