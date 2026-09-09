export function purchaseCta(
  sectionTitle: unknown,
  currentPlan: unknown,
  opts?: { busy?: boolean; canBuy?: boolean },
): { disabled: boolean; label: string };

export function canStartPurchase(productId: unknown, currentPlan: unknown): boolean;
