/** Shared demo workbench: chrome + control state for manifest-driven demos.
 *
 * Pattern: the demo calls `useControlState(defaults, manifest.scenarios)` and
 * passes the returned state object (plus its slot content) to `DemoWorkbench`;
 * every slot reads the same live control values, so controls, canvas and
 * insight rails stay in sync and share one URL-serialized state. */
export { DemoFigure } from "./DemoFigure";
export { DemoWorkbench } from "./DemoWorkbench";
export { KpiTile, type KpiTone } from "./KpiTile";
export { Notice } from "./Notice";
export { useControlState, type ControlState, type ControlValues } from "./useControlState";
