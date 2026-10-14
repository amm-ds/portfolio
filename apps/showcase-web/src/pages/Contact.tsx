import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { SITE_EMAIL } from "../config";

export function Contact() {
  return (
    <>
      <section className="services-hero">
        <p className="kicker">$ contact</p>
        <h1>Get in touch</h1>
        <p className="contact-status">[status] open for freelance and consulting engagements</p>
      </section>

      <Card className="contact-block">
        <ul>
          <li>
            GitHub:{" "}
            <a href="https://github.com/amm-ds" target="_blank" rel="noreferrer">
              github.com/amm-ds
            </a>{" "}
            — fastest way to reach me; open an issue or use the profile contact.
          </li>
          <li>
            Email:{" "}
            <a href={`mailto:${SITE_EMAIL}`}>{SITE_EMAIL}</a>
          </li>
          <li>Languages: English, Spanish.</li>
          <li>Location/timezone: location-independent; flexible overlap with EU and US hours.</li>
          <li>Response time: typical first reply within 48 hours.</li>
        </ul>
      </Card>

      <h2 className="section-title">how engagements start</h2>
      <p className="section-intro">
        A free 30–45 minute discovery call: problem, data reality, constraints, and what
        "done" must look like — followed by a written summary with options and rough scope.
        Fixed-scope pilots come after that.{" "}
        <Link to="/services">see services &amp; process →</Link>
      </p>

      <Card className="cta-band">
        <p>
          <strong>Available now.</strong> Freelance and contract engagements, EU/US timezone
          overlap, typical response within 48 hours.
        </p>
        <p className="cta-links">
          <Link to="/projects">/projects</Link> ·{" "}
          <a href="https://github.com/amm-ds/portfolio" target="_blank" rel="noreferrer">
            github
          </a>
        </p>
      </Card>
    </>
  );
}
