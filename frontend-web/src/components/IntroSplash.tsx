import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { IntroScene } from "./3d/IntroScene";

const SESSION_KEY = "meridiangrid_intro_seen";

const BRAND_LETTERS = "MeridianGrid".split("");

export function IntroSplash({ onDone }: { onDone: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const alreadySeen = sessionStorage.getItem(SESSION_KEY);
    if (reducedMotion || alreadySeen) {
      onDone();
      return;
    }
    setVisible(true);
    // no auto-dismiss timer - stays until the user explicitly presses Skip
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function dismiss() {
    sessionStorage.setItem(SESSION_KEY, "1");
    setVisible(false);
    setTimeout(onDone, 400);
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed inset-0 z-50 bg-[#05070D] flex flex-col items-center justify-center select-none"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="absolute inset-0">
            <IntroScene />
          </div>

          <div className="relative z-10 flex flex-col items-center px-6 text-center">
            <motion.p
              className="text-sm tracking-[0.3em] uppercase text-emerald-400/80 mb-3"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
            >
              Welcome to
            </motion.p>
            <h1 className="font-display text-5xl sm:text-6xl font-bold flex flex-wrap justify-center">
              {BRAND_LETTERS.map((letter, i) => (
                <motion.span
                  key={i}
                  className="bg-gradient-to-br from-emerald-300 via-emerald-400 to-cyan-400 bg-clip-text text-transparent"
                  initial={{ opacity: 0, y: 24, rotateX: -60 }}
                  animate={{ opacity: 1, y: 0, rotateX: 0 }}
                  transition={{ delay: 0.35 + i * 0.045, duration: 0.5, ease: "easeOut" }}
                >
                  {letter}
                </motion.span>
              ))}
            </h1>
            <motion.p
              className="mt-4 text-slate-400 max-w-sm text-sm sm:text-base"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.1, duration: 0.6 }}
            >
              AI-orchestrated EV charging, mapped across India in real time.
            </motion.p>
            <motion.button
              onClick={dismiss}
              className="mt-8 text-xs text-slate-500 hover:text-slate-300 underline underline-offset-4 cursor-pointer"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.6, duration: 0.6 }}
            >
              Skip
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
