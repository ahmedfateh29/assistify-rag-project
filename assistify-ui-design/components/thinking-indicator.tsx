export function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className="flex items-center gap-1 rounded-2xl px-4 py-3 text-sm text-[#232323]"
        style={{ backgroundColor: "#f6c33c" }}
      >
        <span>Thinking</span>
        <span className="dot-1 inline-block">.</span>
        <span className="dot-2 inline-block">.</span>
        <span className="dot-3 inline-block">.</span>
      </div>
    </div>
  );
}
