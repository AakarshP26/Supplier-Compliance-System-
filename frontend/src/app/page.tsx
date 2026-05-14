"use client";

import { useState, useEffect } from "react";
import { MagicCard } from "@/components/ui/magic-card";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { Meteors } from "@/components/ui/meteors";
import { BlurFade } from "@/components/ui/blur-fade";
import axios from "axios";
import { ShieldAlert, CheckCircle, Activity, Globe } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function Home() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    axios.get("http://localhost:8000/api/portfolio-stats")
      .then(res => setStats(res.data))
      .catch(err => console.error("Error fetching stats:", err));
  }, []);

  const features = [
    {
      Icon: ShieldAlert,
      name: "High Risk Suppliers",
      kpi: stats ? `${stats.n_risky}` : "-",
      description: "Suppliers flagged below safe threshold.",
      href: "#",
      cta: "View List",
      className: "col-span-3 lg:col-span-2 shadow-xl",
      background: <div className="absolute inset-0 bg-red-500/5 blur-3xl transition-all duration-500 group-hover:bg-red-500/10" />,
    },
    {
      Icon: CheckCircle,
      name: "Compliance Status",
      kpi: stats ? `${Math.round((stats.n_passed_checks / stats.n_total) * 100)}%` : "-",
      description: "Pass rate across automated checks.",
      href: "#",
      cta: "View Checks",
      className: "col-span-3 lg:col-span-1 shadow-xl",
      background: <div className="absolute inset-0 bg-green-500/5 blur-3xl transition-all duration-500 group-hover:bg-green-500/10" />,
    },
    {
      Icon: Activity,
      name: "Adversarial Labs",
      kpi: "Sim",
      description: "Simulate red-team attacks on scores.",
      href: "/lab",
      cta: "Run Simulation",
      className: "col-span-3 lg:col-span-1 shadow-xl overflow-hidden relative",
      background: (
        <>
          <Meteors number={10} />
          <div className="absolute inset-0 bg-blue-500/5 blur-3xl transition-all duration-500 group-hover:bg-blue-500/10" />
        </>
      ),
    },
    {
      Icon: Globe,
      name: "News Intelligence",
      kpi: stats ? `${stats.n_articles}+` : "-",
      description: "Articles analyzed across 35 countries.",
      href: "#",
      cta: "View Sources",
      className: "col-span-3 lg:col-span-2 shadow-xl",
      background: <div className="absolute inset-0 bg-purple-500/5 blur-3xl transition-all duration-500 group-hover:bg-purple-500/10" />,
    },
  ];

  return (
    <div className="p-8 pb-20">
      <div className="max-w-5xl mx-auto space-y-12 mt-4">
        <BlurFade delay={0.1}>
          <div>
            <h2 className="text-4xl font-semibold tracking-tighter bg-gradient-to-br from-white to-white/50 bg-clip-text text-transparent">Portfolio Overview</h2>
            <p className="text-white/50 mt-3 text-lg font-light">Aggregate risk intelligence across all global seed suppliers.</p>
          </div>
        </BlurFade>

        <BlurFade delay={0.25}>
          <BentoGrid>
            {features.map((feature, idx) => (
              <BentoCard key={idx} {...feature} />
            ))}
          </BentoGrid>
        </BlurFade>
        
        <BlurFade delay={0.4}>
          <MagicCard className="h-96 w-full flex flex-col p-8 border-white/5 bg-black/40 backdrop-blur-sm shadow-2xl" gradientColor="rgba(99,102,241,0.1)">
             <div className="mb-6 flex items-center justify-between">
                 <h3 className="text-xl font-semibold tracking-tight text-white/90">Score Distribution</h3>
                 <span className="text-xs font-medium tracking-widest text-indigo-400 uppercase bg-indigo-500/10 px-3 py-1 rounded-full border border-indigo-500/20">Live</span>
             </div>
             
             <div className="flex-1 w-full min-h-[250px]">
               {stats?.distribution ? (
                 <ResponsiveContainer width="100%" height="100%">
                   <BarChart data={stats.distribution}>
                     <XAxis 
                        dataKey="range" 
                        stroke="rgba(255,255,255,0.3)" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false} 
                        dy={10}
                      />
                     <YAxis 
                        stroke="rgba(255,255,255,0.3)" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false} 
                        dx={-10}
                      />
                     <Tooltip 
                        cursor={{fill: 'rgba(255,255,255,0.05)'}} 
                        contentStyle={{backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px'}} 
                        itemStyle={{color: '#818cf8'}}
                     />
                     <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={40} />
                   </BarChart>
                 </ResponsiveContainer>
               ) : (
                 <div className="w-full h-full bg-gradient-to-r from-indigo-500/5 via-purple-500/5 to-indigo-500/5 rounded-2xl animate-pulse" />
               )}
             </div>
          </MagicCard>
        </BlurFade>
      </div>
    </div>
  );
}
