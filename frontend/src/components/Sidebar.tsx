import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { listJobs } from "../api";

function CopyDatabaseIcon() {
  return (
    <svg className="w-[17px] h-[20px] shrink-0" viewBox="0 0 17 20" fill="currentColor" aria-hidden="true">
      <path d="M12.5263 0H1.78947C0.805263 0 0 0.818182 0 1.81818V14.5455H1.78947V1.81818H12.5263V0ZM15.2105 3.63636H5.36842C4.38421 3.63636 3.57895 4.45455 3.57895 5.45455V18.1818C3.57895 19.1818 4.38421 20 5.36842 20H15.2105C16.1947 20 17 19.1818 17 18.1818V5.45455C17 4.45455 16.1947 3.63636 15.2105 3.63636ZM15.2105 18.1818H5.36842V5.45455H15.2105V18.1818Z" />
    </svg>
  );
}

function InsightsIcon() {
  return (
    <svg className="w-5 h-5 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path d="M0 11.1111H8.88889V0H0V11.1111ZM0 20H8.88889V13.3333H0V20ZM11.1111 20H20V8.88889H11.1111V20ZM11.1111 0V6.66667H20V0H11.1111Z" />
    </svg>
  );
}

function LogsIcon({ className = "w-5 h-2" }: { className?: string }) {
  return (
    <svg className={`${className} shrink-0`} viewBox="0 0 20 8" fill="currentColor" aria-hidden="true">
      <path d="M0 0H20V2.66667H0V0ZM0 5.33333H12.5V8H0V5.33333Z" />
    </svg>
  );
}

export default function Sidebar() {
  const { pathname } = useLocation();
  const [databasesOpen, setDatabasesOpen] = useState(true);
  const [jobsOpen, setJobsOpen] = useState(false);
  const [activeJobsCount, setActiveJobsCount] = useState(0);

  useEffect(() => {
    setDatabasesOpen(pathname === "/" || pathname.startsWith("/agents"));
    setJobsOpen(pathname.startsWith("/jobs"));
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const jobs = await listJobs();
        if (!cancelled) {
          setActiveJobsCount(jobs.filter((job) => ["pending", "leased", "running"].includes(job.status)).length);
        }
      } catch {
        // Non-fatal: the pill just won't update this cycle.
      }
    }

    refresh();
    const handle = setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, []);

  return (
    <aside className="w-[249px] shrink-0 bg-surface flex flex-col">
      <div className="pt-[21px] pl-[25px] pb-[24px]">
        <img src="/icons/icon-cloud-logo.svg" alt="dataferry" className="w-10 h-10" />
      </div>

      <nav className="flex flex-col flex-1 min-h-0">
        <button
          type="button"
          className={`nav-primary-item flex items-center justify-between mx-2 pl-[22px] pr-[12px] py-2 rounded-lg hover:bg-[#454545] transition-colors text-left ${
            databasesOpen ? "text-brand" : "text-white"
          }`}
          aria-expanded={databasesOpen}
          onClick={() => setDatabasesOpen((open) => !open)}
        >
          <span className="flex items-center gap-[11px]">
            <svg className="w-5 h-5 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M10 8.88889C7.22222 8.88889 4.86111 8.4537 2.91667 7.58333C0.972222 6.71296 0 5.66667 0 4.44444C0 3.22222 0.972222 2.17593 2.91667 1.30556C4.86111 0.435185 7.22222 0 10 0C12.7778 0 15.1389 0.435185 17.0833 1.30556C19.0278 2.17593 20 3.22222 20 4.44444C20 5.66667 19.0278 6.71296 17.0833 7.58333C15.1389 8.4537 12.7778 8.88889 10 8.88889ZM10 14.4444C7.22222 14.4444 4.86111 14.0093 2.91667 13.1389C0.972222 12.2685 0 11.2222 0 10V7.22222C0 8.03704 0.37963 8.72704 1.13889 9.29222C1.89815 9.85667 2.80556 10.3148 3.86111 10.6667C4.91667 11.0185 6.01407 11.273 7.15333 11.43C8.29185 11.5878 9.24074 11.6667 10 11.6667C10.7593 11.6667 11.7081 11.5878 12.8467 11.43C13.9859 11.273 15.0833 11.0185 16.1389 10.6667C17.1944 10.3148 18.1019 9.85667 18.8611 9.29222C19.6204 8.72704 20 8.03704 20 7.22222V10C20 11.2222 19.0278 12.2685 17.0833 13.1389C15.1389 14.0093 12.7778 14.4444 10 14.4444ZM10 20C7.22222 20 4.86111 19.5648 2.91667 18.6944C0.972222 17.8241 0 16.7778 0 15.5556V12.7778C0 13.5926 0.37963 14.2826 1.13889 14.8478C1.89815 15.4122 2.80556 15.8704 3.86111 16.2222C4.91667 16.5741 6.01407 16.8289 7.15333 16.9867C8.29185 17.1437 9.24074 17.2222 10 17.2222C10.7593 17.2222 11.7081 17.1437 12.8467 16.9867C13.9859 16.8289 15.0833 16.5741 16.1389 16.2222C17.1944 15.8704 18.1019 15.4122 18.8611 14.8478C19.6204 14.2826 20 13.5926 20 12.7778V15.5556C20 16.7778 19.0278 17.8241 17.0833 18.6944C15.1389 19.5648 12.7778 20 10 20Z" />
            </svg>
            <span className="font-bold text-[13px] tracking-wide">DATABASES</span>
          </span>
          <svg
            className={`collapsible-chevron w-[15px] h-[9px] transition-transform duration-200 ${
              databasesOpen ? "" : "rotate-180"
            }`}
            viewBox="0 0 15 9"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M1.7625 9L7.5 3.43725L13.2375 9L15 7.28745L7.5 0L0 7.28745L1.7625 9Z" />
          </svg>
        </button>

        <div className={`collapsible-content ${databasesOpen ? "" : "collapsed"}`}>
          <div className="relative min-h-0">
            <span className="absolute left-[40px] top-0 bottom-[24px] w-px bg-white/25" aria-hidden="true"></span>
            <ul className="flex flex-col gap-[13px] pt-[13px] pb-[24px]">
              <li>
                <Link
                  to="/"
                  className={`flex items-center gap-[10px] pl-[61px] pr-[20px] py-1 ${
                    pathname === "/" ? "text-brand" : "text-white"
                  }`}
                >
                  <CopyDatabaseIcon />
                  <span className="font-bold text-[12px]">COPY DATABASE</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/agents"
                  className={`flex items-center gap-[10px] pl-[60px] pr-[20px] py-1 ${
                    pathname.startsWith("/agents") ? "text-brand" : "text-white"
                  }`}
                >
                  <InsightsIcon />
                  <span className="font-bold text-[12px]">AGENTS &amp; CONNECTIONS</span>
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <button
          type="button"
          className={`nav-primary-item flex items-center justify-between mx-2 pl-[22px] pr-[12px] py-2 rounded-lg hover:bg-[#454545] transition-colors text-left ${
            jobsOpen ? "text-brand" : "text-white"
          }`}
          aria-expanded={jobsOpen}
          onClick={() => setJobsOpen((open) => !open)}
        >
          <span className="flex items-center gap-[11px]">
            <LogsIcon />
            <span className="font-bold text-[13px] tracking-wide">JOBS</span>
          </span>
          <svg
            className={`collapsible-chevron w-[15px] h-[9px] transition-transform duration-200 ${
              jobsOpen ? "" : "rotate-180"
            }`}
            viewBox="0 0 15 9"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M1.7625 9L7.5 3.43725L13.2375 9L15 7.28745L7.5 0L0 7.28745L1.7625 9Z" />
          </svg>
        </button>

        <div className={`collapsible-content ${jobsOpen ? "" : "collapsed"}`}>
          <div className="relative min-h-0">
            <span className="absolute left-[40px] top-0 bottom-[16px] w-px bg-white/25" aria-hidden="true"></span>
            <ul className="flex flex-col gap-[13px] pt-[13px] pb-[16px]">
              <li>
                <Link
                  to="/jobs"
                  className={`flex items-center gap-[10px] pl-[61px] pr-[20px] py-1 ${
                    jobsOpen ? "text-brand" : "text-white"
                  }`}
                >
                  <svg className="w-5 h-5 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <rect x="0" y="1.5" width="20" height="3" rx="1.5" />
                    <rect x="0" y="8.5" width="20" height="3" rx="1.5" />
                    <rect x="0" y="15.5" width="13" height="3" rx="1.5" />
                  </svg>
                  <span className="font-bold text-[12px]">ALL JOBS</span>
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-auto pt-4 pb-4 border-t border-white/10 flex justify-center">
          <Link
            to="/jobs"
            className={`inline-flex items-center gap-2 rounded-full transition-colors px-4 py-2 ${
              jobsOpen
                ? "bg-[#66BCFA]/15 border border-[#66BCFA]/40 hover:bg-[#66BCFA]/20"
                : "bg-white/5 hover:bg-white/10"
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#66BCFA] animate-pulse" aria-hidden="true"></span>
            <span className="font-bold text-[12px] text-white tracking-wide">
              {activeJobsCount} ACTIVE JOB{activeJobsCount === 1 ? "" : "S"}
            </span>
          </Link>
        </div>
      </nav>
    </aside>
  );
}
