import VisionHero from '@/components/vision/VisionHero';
import ProblemSection from '@/components/vision/ProblemSection';
import HowItWorks from '@/components/vision/HowItWorks';
import CorePillars from '@/components/vision/CorePillars';
import ImpactSection from '@/components/vision/ImpactSection';
import TechShowcase from '@/components/vision/TechShowcase';
import FiveYearVision from '@/components/vision/FiveYearVision';
import PlatformPotential from '@/components/vision/PlatformPotential';

export default function Vision() {
  return (
    <div className="space-y-16">
      <VisionHero />
      <ProblemSection />
      <HowItWorks />
      <CorePillars />
      <ImpactSection />
      <TechShowcase />
      <FiveYearVision />
      <PlatformPotential />
    </div>
  );
}
