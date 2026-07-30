import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import Nav from "../components/Nav";
import Card from "../components/ui/Card";
import Button, { buttonClasses } from "../components/ui/Button";

export default function LandingPage() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-gray-50">
      <Nav />
      <main>
        <section className="bg-gradient-to-br from-brand-blue to-brand-teal px-6 py-20 text-center text-white">
          <h1 className="mx-auto max-w-2xl text-4xl font-bold sm:text-5xl">
            {t("page.landing.hero.headline")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-lg text-white/90">
            {t("page.landing.hero.subtitle")}
          </p>
          <Button
            as="a"
            href="/api/auth/google/login"
            variant="secondary"
            className="mt-8 !bg-white !text-brand-blue"
          >
            {t("nav.loginGoogle")}
          </Button>
        </section>

        <section className="mx-auto max-w-5xl px-6 py-16">
          <h2 className="text-center text-2xl font-bold text-gray-800">
            {t("page.landing.features.title")}
          </h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            <Card padded={false} className="overflow-hidden">
              <img src="/track.png" alt="" className="h-40 w-full object-cover" />
              <div className="p-4">
                <h3 className="text-lg font-semibold text-brand-blue">
                  {t("page.landing.features.track.title")}
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  {t("page.landing.features.track.description")}
                </p>
              </div>
            </Card>
            <Card padded={false} className="overflow-hidden">
              <img src="/park.png" alt="" className="h-40 w-full object-cover" />
              <div className="p-4">
                <h3 className="text-lg font-semibold text-brand-blue">
                  {t("page.landing.features.park.title")}
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  {t("page.landing.features.park.description")}
                </p>
              </div>
            </Card>
            <Card padded={false} className="overflow-hidden">
              <img src="/notify.png" alt="" className="h-40 w-full object-cover" />
              <div className="p-4">
                <h3 className="text-lg font-semibold text-brand-blue">
                  {t("page.landing.features.notify.title")}
                </h3>
                <p className="mt-2 text-sm text-gray-600">
                  {t("page.landing.features.notify.description")}
                </p>
              </div>
            </Card>
          </div>
        </section>

        <section className="border-t border-gray-200 bg-white px-6 py-16 text-center">
          <h2 className="text-xl font-semibold text-gray-800">
            {t("page.landing.citiesCta.title")}
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
            {t("page.landing.citiesCta.subtitle")}
          </p>
          <Link to="/map" className={`${buttonClasses("secondary", "md")} mt-6`}>
            {t("page.landing.citiesCta.cta")}
          </Link>
        </section>

        <section className="border-t border-gray-200 bg-gray-50 px-6 py-16 text-center">
          <h2 className="text-xl font-semibold text-gray-800">
            {t("page.landing.openSource.title")}
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
            {t("page.landing.openSource.subtitle")}
          </p>
          <a
            href="https://github.com/jmalvarezf-lmes/personal-mobility-manager"
            target="_blank"
            rel="noreferrer"
            className={`${buttonClasses("secondary", "md")} mt-6 gap-2`}
          >
            <svg viewBox="0 0 19 19" className="h-5 w-5" aria-hidden="true">
              <use href="/icons.svg#github-icon" />
            </svg>
            {t("page.landing.openSource.cta")}
          </a>
        </section>
      </main>
    </div>
  );
}
