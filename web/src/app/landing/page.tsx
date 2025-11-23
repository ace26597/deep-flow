// Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
// SPDX-License-Identifier: MIT

import { useTranslations } from 'next-intl';
import { useMemo } from "react";

import { SiteHeader } from "../chat/components/site-header";
import { Jumbotron } from "./components/jumbotron";
import { Ray } from "./components/ray";
import { CaseStudySection } from "./sections/case-study-section";
import { MultiAgentSection } from "./sections/multi-agent-section";

export default function LandingPage() {
    return (
        <div className="flex flex-col items-center">
            <SiteHeader />
            <main className="container flex flex-col items-center justify-center gap-56">
                <Jumbotron />
                <CaseStudySection />
                <MultiAgentSection />
            </main>
            <Footer />
            <Ray />
        </div>
    );
}

function Footer() {
    const t = useTranslations('footer');
    const year = useMemo(() => new Date().getFullYear(), []);
    return (
        <footer className="container mt-32 flex flex-col items-center justify-center">
            <hr className="from-border/0 via-border/70 to-border/0 m-0 h-px w-full border-none bg-gradient-to-r" />
            <div className="text-muted-foreground container flex h-20 flex-col items-center justify-center text-sm">

            </div>
            <div className="text-muted-foreground container mb-8 flex flex-col items-center justify-center text-xs">

                <p>&copy; {year} {t('copyright')}</p>
            </div>
        </footer>
    );
}
