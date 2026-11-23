import { type CourseOut, CourseService, type LevelOut } from "@/client";

export type Course = CourseOut & { topLevel: LevelOut };

export const courseQuery = {
  queryKey: ["course"],
  queryFn: async (): Promise<Course> => {
    const course = (await CourseService.course()).data;
    const topLevel = course.levels.at(-1);
    if (!topLevel) throw new Error("The Course has no Self-assessment level");
    return { ...course, topLevel };
  },
  staleTime: Number.POSITIVE_INFINITY,
};
