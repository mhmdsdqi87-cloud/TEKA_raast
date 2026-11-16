// Deliberate fixture component for the compat matrix (Angular stack).
// The decorator points at external template and stylesheet files; the
// component class itself only carries Persian view-model strings, so it
// must stay silent. The scannable defect pair lives in the stylesheet.
// Decorator wiring and ViewEncapsulation rewriting are not modeled.
import { Component } from "@angular/core";

@Component({
  selector: "app-root",
  templateUrl: "./app.component.html",
  styleUrls: ["./app.component.css"],
})
export class AppComponent {
  readonly title = "سبد خرید";
  readonly emptyHint = "سبد خالی است";
}
