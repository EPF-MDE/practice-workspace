import { type CourseOut, CourseService } from "@/client";

export const courseQuery = {
  queryKey: ["course"],
  queryFn: async (): Promise<CourseOut> => (await CourseService.course()).data,
  staleTime: Number.POSITIVE_INFINITY,
};
