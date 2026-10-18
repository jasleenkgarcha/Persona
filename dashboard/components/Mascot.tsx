export default function Mascot({
  tone = "on-light",
  className,
}: {
  tone?: "on-light" | "on-dark";
  className?: string;
}) {
  const onDark = tone === "on-dark";
  const body = onDark ? "#ffffff" : "#0d1b2a";
  const screen = onDark ? "#0d1b2a" : "#16324f";
  const ink = "#7dd3e8";
  const bar = onDark ? "#c5d0dc" : "#7dd3e8";
  const badge = onDark ? "#7dd3e8" : "#ffffff";
  const badgeInk = "#0d1b2a";

  return (
    <svg className={className} viewBox="0 0 160 168" fill="none" aria-hidden="true">
      <path d="M24 98c-14-16-14-44 0-60" stroke={ink} strokeWidth="3" strokeLinecap="round" opacity="0.35" />
      <path d="M34 92c-8-11-8-30 0-41" stroke={ink} strokeWidth="3" strokeLinecap="round" />
      <rect x="46" y="16" width="84" height="128" rx="22" fill={body} />
      <rect x="56" y="30" width="64" height="86" rx="14" fill={screen} />
      <circle cx="76" cy="66" r="5.5" fill={ink} />
      <circle cx="100" cy="66" r="5.5" fill={ink} />
      <circle cx="77.6" cy="67.2" r="2.1" fill={screen} />
      <circle cx="101.6" cy="67.2" r="2.1" fill={screen} />
      <path d="M78 84c5 6 15 6 20 0" stroke={ink} strokeWidth="2.6" strokeLinecap="round" />
      <rect x="78" y="126" width="20" height="5" rx="2.5" fill={bar} />
      <circle cx="122" cy="128" r="18" fill={badge} />
      <path d="M122 118.2 131.2 121.8v7.4c0 5.8-9.2 10.6-9.2 10.6s-9.2-4.8-9.2-10.6v-7.4l9.2-3.6Z" fill={badgeInk} />
      <path d="M117.2 128.4 120.5 131.6 127.2 124.8" stroke={ink} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
