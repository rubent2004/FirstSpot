/**
 * El Salvador's 14 departments, keyed by the first two digits of the DIGESTYC
 * district code ("060101" is district 01 of municipality 06 01, in department
 * 06). The API names districts but not their department; the code prefix is the
 * documented hierarchy (backend census geo_codes), so the department is derived
 * rather than fetched. Proper nouns, identical in es and en.
 */
const DEPARTMENTS: Readonly<Record<string, string>> = {
  "01": "Ahuachapán",
  "02": "Santa Ana",
  "03": "Sonsonate",
  "04": "Chalatenango",
  "05": "La Libertad",
  "06": "San Salvador",
  "07": "Cuscatlán",
  "08": "La Paz",
  "09": "Cabañas",
  "10": "San Vicente",
  "11": "Usulután",
  "12": "San Miguel",
  "13": "Morazán",
  "14": "La Unión",
};

function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim()
    .toLowerCase();
}

/** Department name for a district code, or null when the prefix is unknown. */
export function departmentName(districtCode: string): string | null {
  return DEPARTMENTS[districtCode.slice(0, 2)] ?? null;
}

/** Code prefix for a department name, ignoring accents and case; null if unknown. */
export function departmentPrefix(name: string | null | undefined): string | null {
  if (!name) return null;
  const wanted = fold(name);
  const hit = Object.entries(DEPARTMENTS).find(([, label]) => fold(label) === wanted);
  return hit ? hit[0] : null;
}
