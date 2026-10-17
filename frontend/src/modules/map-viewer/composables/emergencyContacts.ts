/**
 * Emergency lines for El Salvador: the single source for the hazard card and
 * for the printed sheet. They are Salvadoran numbers, so a print of an area
 * outside El Salvador must not list them.
 */
export interface EmergencyContact {
  id: "national" | "civilProtection" | "redCross" | "fire";
  /** Digits only, as dialled. */
  dial: string;
  /** How the number is read. */
  display: string;
}

export const EMERGENCY_CONTACTS: readonly EmergencyContact[] = [
  { id: "national", dial: "911", display: "911" },
  { id: "civilProtection", dial: "22810888", display: "2281-0888" },
  { id: "redCross", dial: "22225155", display: "2222-5155" },
  { id: "fire", dial: "913", display: "913" },
];
