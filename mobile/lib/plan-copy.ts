import {
  displayPlanLabel,
  ELITE_LINEUP_COPY,
  PRO_LINEUP_COPY,
} from "./apple-catalog.mjs";

export { displayPlanLabel, ELITE_LINEUP_COPY, PRO_LINEUP_COPY };

export function lineupLimitForPlan(plan: unknown, hasAccess?: boolean): number {
  const label = displayPlanLabel(plan as string, hasAccess);
  if (label === "Elite Stack") return 150;
  if (label === "Pro Arena") return 20;
  return 1;
}

export function lineupCopyForPlan(plan: unknown, hasAccess?: boolean): string {
  const label = displayPlanLabel(plan as string, hasAccess);
  if (label === "Elite Stack") return ELITE_LINEUP_COPY;
  if (label === "Pro Arena") return PRO_LINEUP_COPY;
  return "1 lineup per slate on Starter";
}
