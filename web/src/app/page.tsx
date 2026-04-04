import Link from "next/link";
import { ArrowRight, Trophy, Zap, LineChart, Target, Shield } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="flex-1 overflow-y-auto w-full">
      {/* Header */}
      <header className="fixed top-0 w-full z-50 glass border-b border-border/50">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded bg-primary flex items-center justify-center font-bold text-white shadow-lg shadow-primary/20">A</div>
            <span className="text-xl font-bold tracking-tight">Apex DFS AI</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Features</Link>
            <Link href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Pricing</Link>
            <Link href="/dashboard" className="text-sm font-medium bg-primary text-primary-foreground px-4 py-2 rounded-full hover:bg-primary/90 transition-all shadow-lg shadow-primary/20">
              Launch App
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 lg:pt-48 lg:pb-32 overflow-hidden min-h-screen flex items-center">
        {/* Background Gradients */}
        <div className="absolute top-1/4 -left-1/4 w-1/2 h-1/2 bg-primary/20 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-1/4 -right-1/4 w-1/2 h-1/2 bg-blue-500/20 rounded-full blur-[120px] pointer-events-none" />
        
        <div className="container mx-auto px-6 relative z-10 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary/50 border border-border text-sm text-primary mb-8 animate-fade-in">
            <Zap className="size-4" />
            <span>V2.0 Now Live - Next Gen Optimization</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8 bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 max-w-4xl mx-auto leading-tight">
            Dominate DFS with <br /> Advanced Machine Learning
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            The most powerful MLB and NBA lineup optimizer. Powered by continuous XGBoost modeling, live Vegas odds integration, and 150-max SCIP generation engine.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/dashboard" className="flex items-center gap-2 bg-primary text-primary-foreground px-8 py-4 rounded-full text-lg font-medium hover:bg-primary/90 hover:scale-105 transition-all shadow-xl shadow-primary/20">
              Start Building Lineups
              <ArrowRight className="size-5" />
            </Link>
            <Link href="#pricing" className="px-8 py-4 rounded-full text-lg font-medium text-foreground bg-secondary hover:bg-secondary/80 border border-border transition-all">
              View Pricing
            </Link>
          </div>

          <div className="mt-20 pt-10 border-t border-border/50 max-w-3xl mx-auto">
            <p className="text-sm text-muted-foreground mb-6 uppercase tracking-wider font-medium">Supported Platforms & Sports</p>
            <div className="flex justify-center gap-8 md:gap-16 opacity-70 grayscale">
              <span className="text-xl font-bold tracking-tight">DraftKings</span>
              <span className="text-xl font-bold tracking-tight text-blue-400">FanDuel</span>
              <span className="text-xl font-bold tracking-tight text-orange-500">NBA</span>
              <span className="text-xl font-bold tracking-tight">MLB</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-card relative">
        <div className="container mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Everything You Need to Win</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">Pro-level tools simplified into a beautiful, lightning-fast dashboard.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={Target}
              title="XGBoost Projections"
              desc="Machine learning models trained continuously on live data, back-tested daily for lowest MAE."
            />
            <FeatureCard 
              icon={LineChart}
              title="Vegas Odds Integration"
              desc="Live parsing of implied team totals, spreads, and market movers pushed directly into player bumps."
            />
            <FeatureCard 
              icon={Shield}
              title="Advanced Rules"
              desc="150-max generation with precise ownership fades, stacking logic, and min-uniqueness controls."
            />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24">
        <div className="container mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Simple, Transparent Pricing</h2>
            <p className="text-muted-foreground">Unlock your edge today.</p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <PricingCard title="Starter" price="$0" features={["1 Lineup Generation", "Basic Projections", "No CSV Export"]} />
            <PricingCard title="Pro" price="$29" featured features={["20 Lineup Generation", "Full ML Projections", "CSV Exports", "Live News Bumps"]} />
            <PricingCard title="Elite" price="$49" features={["150 Lineup Generation", "Advanced Exposures", "Backtesting Dashboard", "Priority Support"]} />
          </div>
        </div>
      </section>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, desc }: any) {
  return (
    <div className="glass p-8 rounded-2xl flex flex-col items-center text-center hover:-translate-y-1 transition-transform duration-300">
      <div className="size-14 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-6">
        <Icon className="size-7" />
      </div>
      <h3 className="text-xl font-bold mb-3">{title}</h3>
      <p className="text-muted-foreground">{desc}</p>
    </div>
  );
}

function PricingCard({ title, price, features, featured = false }: any) {
  return (
    <div className={`p-8 rounded-2xl border ${featured ? 'bg-primary/5 border-primary shadow-xl shadow-primary/10 relative transform md:-translate-y-4' : 'glass border-border'}`}>
      {featured && <div className="absolute top-0 right-1/2 translate-x-1/2 -translate-y-1/2 bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Most Popular</div>}
      <h3 className="text-xl font-medium mb-2">{title}</h3>
      <div className="text-4xl font-bold mb-6">{price}<span className="text-lg text-muted-foreground font-normal">/mo</span></div>
      <ul className="space-y-4 mb-8 flex-1">
        {features.map((f: string, i: number) => (
          <li key={i} className="flex items-center gap-3">
            <Trophy className="size-4 text-primary" />
            <span className="text-neon-green">SPORTSBOOK ME DFS AI</span>
          </li>
        ))}
      </ul>
      <button className={`w-full py-3 rounded-lg font-medium transition-colors ${featured ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-secondary text-foreground hover:bg-secondary/80'}`}>
        Choose {title}
      </button>
    </div>
  );
}
