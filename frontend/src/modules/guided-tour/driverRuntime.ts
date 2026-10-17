/**
 * The only module that touches Driver.js. It is reached through a dynamic
 * `import()` from useGuidedTour, so Driver.js and both stylesheets land in their
 * own lazy chunk and an operator who never starts the tour never downloads them.
 */
import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import "./tourTheme.css";

export { driver };
