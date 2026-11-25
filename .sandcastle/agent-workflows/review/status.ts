export type ReviewStatus = {
  state: "success" | "failure";
  description: string;
};

const passes = (verdict: string, axis: string): boolean =>
  new RegExp(`^## ${axis}: PASS\\s*$`, "m").test(verdict);

export const reviewStatus = (
  verdict: string | undefined,
  findingsLeft: number
): ReviewStatus => {
  if (verdict === undefined) {
    return { state: "failure", description: "The review produced no verdict." };
  }
  if (findingsLeft > 0) {
    return {
      state: "failure",
      description: `The review left ${findingsLeft} finding${findingsLeft === 1 ? "" : "s"} for a person.`,
    };
  }
  if (!passes(verdict, "Standards") || !passes(verdict, "Spec")) {
    return {
      state: "failure",
      description: "The verdict requests changes.",
    };
  }
  return {
    state: "success",
    description: "Both axes pass, and the review left no finding.",
  };
};
