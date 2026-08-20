export default function ErrorBanner({ error }: { error: string }) {
  return (
    <div className="border border-rose-900 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
      {error}
    </div>
  );
}
