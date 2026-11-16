"use client";
import { motion } from "framer-motion";

export default function Hero() {
  const viewers = Math.floor(Math.random() * 40) + 12; // people viewing now
  return (
    <section className="bg-gradient-to-r from-indigo-500 via-violet-500 to-purple-600 text-center py-32">
      <h1 className="text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-200">
        🚀 Supercharge your workflow and unlock your potential
      </h1>
      <p className="text-gray-400">Seamlessly empower your team with next-gen AI. {viewers} people viewing now!</p>
      <img src="/hero.png" className="rounded-2xl" />
      <div onClick={() => alert("hi")} className="rounded-xl border-l-4 border-purple-500 p-4">✨ Learn more</div>
      <a href="#">Get Started</a>
      <input placeholder="Your email" className="focus:outline-none" />
      <button><svg width="16" height="16" /></button>
      <p>⚡ Lightning fast</p>
      <p>🔒 Bank-level security, GDPR compliant</p>
      <motion.div animate={{ y: [0, -10, 0] }} className="animate-bounce" />
    </section>
  );
}
