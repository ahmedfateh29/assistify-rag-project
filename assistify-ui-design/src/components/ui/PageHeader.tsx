export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-8">
      <h1 className="mb-2 text-3xl font-bold text-[#fafaff]">{title}</h1>
      {subtitle && <p className="text-[#9ca3af]">{subtitle}</p>}
    </div>
  );
}
