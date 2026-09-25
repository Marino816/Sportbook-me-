/** Canonical Sportbook Me website prices and checkout plan names. */

export const WEBSITE_PRICES = {
  proMonthly: 49.99,
  proAnnual: 399.99,
  eliteMonthly: 89.99,
  eliteAnnual: 599.99,
} as const;

export const WEBSITE_CHECKOUT_PLANS = {
  proMonthly: "Pro Arena",
  proAnnual: "Pro Arena Annual",
  eliteMonthly: "Elite Stack",
  eliteAnnual: "Elite Stack Annual",
} as const;

export function formatUsd(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

export function splitUsd(amount: number): { dollars: string; cents: string } {
  const [dollars, cents] = amount.toFixed(2).split(".");
  return { dollars: `$${Number(dollars)}`, cents };
}

const proMonthlyParts = splitUsd(WEBSITE_PRICES.proMonthly);
const eliteMonthlyParts = splitUsd(WEBSITE_PRICES.eliteMonthly);
const proAnnualParts = splitUsd(WEBSITE_PRICES.proAnnual);
const eliteAnnualParts = splitUsd(WEBSITE_PRICES.eliteAnnual);

export const WEBSITE_PRICE_DISPLAY = {
  proMonthlyDollars: proMonthlyParts.dollars,
  proMonthlyPeriod: `.${proMonthlyParts.cents}/mo`,
  proAnnualDollars: proAnnualParts.dollars,
  proAnnualPeriod: `.${proAnnualParts.cents}/yr`,
  proAnnualLine: `or ${formatUsd(WEBSITE_PRICES.proAnnual)}/year`,
  eliteMonthlyDollars: eliteMonthlyParts.dollars,
  eliteMonthlyPeriod: `.${eliteMonthlyParts.cents}/mo`,
  eliteAnnualDollars: eliteAnnualParts.dollars,
  eliteAnnualPeriod: `.${eliteAnnualParts.cents}/yr`,
  eliteAnnualLine: `or ${formatUsd(WEBSITE_PRICES.eliteAnnual)}/year`,
  proMonthlyLegal: `${formatUsd(WEBSITE_PRICES.proMonthly)}/month`,
  proAnnualLegal: `${formatUsd(WEBSITE_PRICES.proAnnual)}/year`,
  eliteMonthlyLegal: `${formatUsd(WEBSITE_PRICES.eliteMonthly)}/month`,
  eliteAnnualLegal: `${formatUsd(WEBSITE_PRICES.eliteAnnual)}/year`,
} as const;

function annualSavings(monthly: number, annual: number): number {
  return Math.round(monthly * 12 - annual);
}

export const WEBSITE_PRICE_SAVINGS = {
  proAnnualVsMonthly: annualSavings(WEBSITE_PRICES.proMonthly, WEBSITE_PRICES.proAnnual),
  eliteAnnualVsMonthly: annualSavings(WEBSITE_PRICES.eliteMonthly, WEBSITE_PRICES.eliteAnnual),
  eliteAnnualMonthlyEquivalent: (WEBSITE_PRICES.eliteAnnual / 12).toFixed(2),
  proAnnualMonthsFree: Math.round(12 - WEBSITE_PRICES.proAnnual / WEBSITE_PRICES.proMonthly),
} as const;
