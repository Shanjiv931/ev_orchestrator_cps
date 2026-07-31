import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

export const resources = {
  en: {
    translation: {
      appName: "EV Orchestrator",
      nav: {
        map: "Map",
        stations: "Stations",
        vehicles: "My Vehicles",
        sessions: "Sessions",
        admin: "City Admin",
        logout: "Log out",
      },
      auth: {
        login: "Log in",
        register: "Create account",
        name: "Full name",
        email: "Email",
        password: "Password",
        persona: "I am a",
        submit: "Continue",
        haveAccount: "Already have an account?",
        needAccount: "Need an account?",
        error: "Something went wrong. Check your details and try again.",
      },
      persona: {
        individual_driver: "Individual driver",
        fleet_operator: "Fleet / depot operator",
        housing_society_resident: "Housing society resident",
        city_admin: "Vellore admin / DISCOM viewer",
      },
      stations: {
        title: "Charging & swap stations",
        connector: "Connector",
        chemistry: "Chemistry",
        chargers: "Chargers",
        swapSlots: "Swap slots",
        safety: "Safety",
        recommend: "Find best station",
        solo: "Traveling alone",
        noResults: "No compatible stations found.",
        distanceKm: "{{km}} km away",
      },
      vehicles: {
        title: "My vehicles",
        add: "Add vehicle",
        class: "Vehicle class",
        connector: "Connector type",
        chemistry: "Battery chemistry",
        pluggable: "Plug-in capable",
        soh: "State of Health (SoH)",
        soc: "State of Charge (SoC)",
        monthsTo80: "Months to 80% threshold",
        trend: "Trend",
      },
      sessions: {
        title: "Charging sessions",
        start: "Start session",
        complete: "Complete session",
        emergency: "Emergency priority",
        energy: "Energy delivered (kWh)",
        cost: "Cost (INR)",
        pay: "Pay at station",
        carbonSummary: "CO2 avoided",
      },
      admin: {
        title: "Vellore admin dashboard",
        demandForecast: "Demand forecast",
        gridStress: "Feeder load",
        stressTest: "Mass-gathering stress test",
        whatIf: "What-if: all vehicles were EV",
        runStressTest: "Run stress test",
      },
      offline: {
        banner: "You're offline - showing the last known station list.",
      },
      common: {
        loading: "Loading...",
        save: "Save",
        cancel: "Cancel",
      },
    },
  },
  hi: {
    translation: {
      appName: "ईवी ऑर्केस्ट्रेटर",
      nav: {
        map: "नक़्शा",
        stations: "स्टेशन",
        vehicles: "मेरे वाहन",
        sessions: "सत्र",
        admin: "शहर प्रशासन",
        logout: "लॉग आउट",
      },
      auth: {
        login: "लॉग इन करें",
        register: "खाता बनाएं",
        name: "पूरा नाम",
        email: "ईमेल",
        password: "पासवर्ड",
        persona: "मैं हूँ",
        submit: "जारी रखें",
        haveAccount: "पहले से खाता है?",
        needAccount: "खाता चाहिए?",
        error: "कुछ गलत हो गया। कृपया विवरण जांचें और फिर प्रयास करें।",
      },
      persona: {
        individual_driver: "व्यक्तिगत चालक",
        fleet_operator: "फ्लीट / डिपो संचालक",
        housing_society_resident: "हाउसिंग सोसाइटी निवासी",
        city_admin: "वेल्लोर प्रशासन / डिस्कॉम व्यूअर",
      },
      stations: {
        title: "चार्जिंग और स्वैप स्टेशन",
        connector: "कनेक्टर",
        chemistry: "बैटरी प्रकार",
        chargers: "चार्जर",
        swapSlots: "स्वैप स्लॉट",
        safety: "सुरक्षा",
        recommend: "सर्वश्रेष्ठ स्टेशन खोजें",
        solo: "अकेले यात्रा कर रहे हैं",
        noResults: "कोई उपयुक्त स्टेशन नहीं मिला।",
        distanceKm: "{{km}} किमी दूर",
      },
      vehicles: {
        title: "मेरे वाहन",
        add: "वाहन जोड़ें",
        class: "वाहन श्रेणी",
        connector: "कनेक्टर प्रकार",
        chemistry: "बैटरी प्रकार",
        pluggable: "प्लग-इन सक्षम",
        soh: "बैटरी स्वास्थ्य (SoH)",
        soc: "चार्ज स्तर (SoC)",
        monthsTo80: "80% सीमा तक महीने",
        trend: "रुझान",
      },
      sessions: {
        title: "चार्जिंग सत्र",
        start: "सत्र शुरू करें",
        complete: "सत्र पूरा करें",
        emergency: "आपातकालीन प्राथमिकता",
        energy: "ऊर्जा (kWh)",
        cost: "लागत (₹)",
        pay: "स्टेशन पर भुगतान करें",
        carbonSummary: "बचाई गई CO2",
      },
      admin: {
        title: "वेल्लोर प्रशासन डैशबोर्ड",
        demandForecast: "मांग पूर्वानुमान",
        gridStress: "फीडर लोड",
        stressTest: "भीड़ तनाव परीक्षण",
        whatIf: "यदि सभी वाहन ईवी होते",
        runStressTest: "तनाव परीक्षण चलाएं",
      },
      offline: {
        banner: "आप ऑफ़लाइन हैं - अंतिम ज्ञात स्टेशन सूची दिखा रहे हैं।",
      },
      common: {
        loading: "लोड हो रहा है...",
        save: "सहेजें",
        cancel: "रद्द करें",
      },
    },
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });

export default i18n;
