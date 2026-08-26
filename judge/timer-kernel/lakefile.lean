import Lake

open System Lake DSL

package kernel where
  version := v!"0.1.0"

require lean4export from git
  "https://github.com/leanprover/lean4export" @
    "15f6055e299ad5b89345e533cc2192f4cc00f659"

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
