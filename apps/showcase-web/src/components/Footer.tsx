export function Footer() {
  return (
    <footer className="footer">
      <p className="status-line">
        amm-ds ~ main<span className="sep">●</span>reproducible
        <span className="sep">●</span>MIT
      </p>
      <p>
        Code released under the{" "}
        <a href="https://github.com/amm-ds/portfolio/blob/main/LICENSE" target="_blank" rel="noreferrer">
          MIT license
        </a>
        . Datasets remain subject to their own licenses, documented per project in the{" "}
        <a href="https://github.com/amm-ds/portfolio" target="_blank" rel="noreferrer">
          repository
        </a>
        .
      </p>
    </footer>
  );
}
