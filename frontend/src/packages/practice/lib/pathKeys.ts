export const pathsKey = ["path"] as const;

export const pathKey = (competency: string) => [...pathsKey, competency];
