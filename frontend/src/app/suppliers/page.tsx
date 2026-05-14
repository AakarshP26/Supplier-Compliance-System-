"use client";

export default function SuppliersPage() {
  return (
    <div className="flex h-full bg-black/95">
      <div className="flex-1 p-8 overflow-y-auto">
        <div className="max-w-5xl mx-auto space-y-8">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">Suppliers Directory</h2>
            <p className="text-white/60 mt-2">View and manage all onboarded suppliers.</p>
          </div>
          
          <div className="h-96 flex items-center justify-center border border-white/10 bg-black/40 rounded-xl">
             <div className="text-center">
                 <p className="text-white/50 mb-4">[ Data Table Component Coming Soon ]</p>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}