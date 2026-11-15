import { httpApi } from "./client";
import { fixtureApi } from "./fixtures";
import type { WorkbenchApi } from "./types";

export const IS_FIXTURE_MODE = import.meta.env.VITE_MOCK === "1";
export const api: WorkbenchApi = IS_FIXTURE_MODE ? fixtureApi : httpApi;
