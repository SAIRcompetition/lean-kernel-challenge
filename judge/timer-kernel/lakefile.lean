import Lake

open System Lake DSL

package kernel where
  version := v!"0.1.0"

require lean4export from git
  "https://github.com/leanprover/lean4export" @
    "3de59f10bc4b4a0f2de698597aeb1246caa0df0a"

require Lean4Checker from git
  "https://github.com/leanprover/lean4checker" @
    "b7398199245524275543dec6113229c9bb4902e5"

target timerControlO pkg : FilePath := do
  let objectFile := pkg.buildDir / "c" / "timer_control.o"
  let sourceJob ← inputTextFile <| pkg.dir / "timer_control.c"
  let lean ← getLeanInstall
  buildO objectFile sourceJob #["-I", lean.includeDir.toString]

extern_lib leanKernelTimerControl pkg := do
  let objectFile ← timerControlO.fetch
  buildStaticLib
    (pkg.staticLibDir / nameToStaticLib "lean_kernel_timer_control")
    #[objectFile]

@[default_target]
lean_exe kernel where
  root := `Main
