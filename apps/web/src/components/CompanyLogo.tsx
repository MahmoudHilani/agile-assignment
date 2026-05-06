export default function CompanyLogo() {
  return (
    <div className="company-logo" aria-label="Hexagon Labs">
      <svg className="company-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <path
          d="M16 2.75 27.47 9.38v13.24L16 29.25 4.53 22.62V9.38L16 2.75Z"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path
          d="M16 9.25 22.06 12.75v7L16 23.25 9.94 19.75v-7L16 9.25Z"
          fill="currentColor"
        />
      </svg>
      <span className="company-name">Hexagon Labs</span>
    </div>
  );
}
