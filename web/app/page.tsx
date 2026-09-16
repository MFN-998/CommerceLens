export default function Home() {
  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 sm:px-10">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 py-7">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="grid size-9 place-items-center rounded-lg bg-slate-900 text-sm font-bold text-white">
            CL
          </span>
          <span className="text-lg font-semibold tracking-tight">CommerceLens</span>
        </div>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
          In development
        </span>
      </header>

      <main className="flex flex-1 flex-col justify-center py-16 sm:py-24">
        <p className="mb-5 text-xs font-semibold tracking-[0.18em] text-indigo-700 uppercase">
          E-commerce analytics &amp; decision intelligence
        </p>
        <h1 className="max-w-3xl text-4xl leading-tight font-semibold tracking-tight sm:text-6xl">
          From commerce data<br className="hidden sm:block" /> to business decisions.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
          A place to understand business performance, investigate customer behavior,
          and turn reliable evidence into better decisions.
        </p>

        <section aria-labelledby="foundation-title" className="mt-12 rounded-2xl border border-slate-200 bg-white p-7 sm:p-9">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="foundation-title" className="text-lg font-semibold">The foundation comes first.</h2>
            <span className="rounded-md bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">Phase 1</span>
          </div>
          <p className="mt-3 max-w-2xl leading-7 text-slate-600">
            This is the initial CommerceLens application. Data preparation and analytics
            will be introduced in the next stages of the project.
          </p>
          <div className="mt-7 border-t border-slate-100 pt-6">
            <p className="text-sm font-semibold text-slate-800">No business data loaded yet</p>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              The planned demonstration uses historical, anonymized transactions from
              the Olist Brazilian E-Commerce dataset. It will not represent a live business feed.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-6 text-xs leading-6 text-slate-500">
        CommerceLens · Project foundation · Historical data, clearly explained.
      </footer>
    </div>
  );
}
