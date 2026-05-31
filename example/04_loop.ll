; ModuleID = '04_loop.c'
source_filename = "04_loop.c"
target datalayout = "e-m:e-p:64:64-i64:64-i128:128-n32:64-S128"
target triple = "riscv64-unknown-none-elf"

; Function Attrs: nofree norecurse nosync nounwind memory(none)
define dso_local float @sum_to(float noundef %0) local_unnamed_addr #0 {
  %2 = fcmp ogt float %0, 1.000000e+00
  br i1 %2, label %3, label %9

3:                                                ; preds = %1, %3
  %4 = phi float [ %7, %3 ], [ 1.000000e+00, %1 ]
  %5 = phi float [ %6, %3 ], [ 1.000000e+00, %1 ]
  %6 = fmul float %5, %4
  %7 = fadd float %4, 1.000000e+00
  %8 = fcmp olt float %7, %0
  br i1 %8, label %3, label %9, !llvm.loop !4

9:                                                ; preds = %3, %1
  %10 = phi float [ 1.000000e+00, %1 ], [ %6, %3 ]
  ret float %10
}

; Function Attrs: nofree norecurse nosync nounwind memory(none)
define dso_local signext i32 @main() local_unnamed_addr #0 {
  br label %1

1:                                                ; preds = %1, %0
  %2 = phi i32 [ 1, %0 ], [ %6, %1 ]
  %3 = phi float [ 1.000000e+00, %0 ], [ %5, %1 ]
  %4 = sitofp i32 %2 to float
  %5 = fmul float %3, %4
  %6 = add nuw nsw i32 %2, 1
  %7 = icmp eq i32 %6, 5
  br i1 %7, label %8, label %1, !llvm.loop !4

8:                                                ; preds = %1
  %9 = fptosi float %5 to i32
  ret i32 %9
}

attributes #0 = { nofree norecurse nosync nounwind memory(none) "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="generic-rv64" "target-features"="+64bit,+d,+f,+m,+relax,+zicsr,-a,-c,-e,-experimental-smaia,-experimental-ssaia,-experimental-zacas,-experimental-zfa,-experimental-zfbfmin,-experimental-zicond,-experimental-zihintntl,-experimental-ztso,-experimental-zvbb,-experimental-zvbc,-experimental-zvfbfmin,-experimental-zvfbfwma,-experimental-zvkg,-experimental-zvkn,-experimental-zvknc,-experimental-zvkned,-experimental-zvkng,-experimental-zvknha,-experimental-zvknhb,-experimental-zvks,-experimental-zvksc,-experimental-zvksed,-experimental-zvksg,-experimental-zvksh,-experimental-zvkt,-h,-save-restore,-svinval,-svnapot,-svpbmt,-v,-xcvbitmanip,-xcvmac,-xsfcie,-xsfvcp,-xtheadba,-xtheadbb,-xtheadbs,-xtheadcmo,-xtheadcondmov,-xtheadfmemidx,-xtheadmac,-xtheadmemidx,-xtheadmempair,-xtheadsync,-xtheadvdot,-xventanacondops,-zawrs,-zba,-zbb,-zbc,-zbkb,-zbkc,-zbkx,-zbs,-zca,-zcb,-zcd,-zce,-zcf,-zcmp,-zcmt,-zdinx,-zfh,-zfhmin,-zfinx,-zhinx,-zhinxmin,-zicbom,-zicbop,-zicboz,-zicntr,-zifencei,-zihintpause,-zihpm,-zk,-zkn,-zknd,-zkne,-zknh,-zkr,-zks,-zksed,-zksh,-zkt,-zmmul,-zve32f,-zve32x,-zve64d,-zve64f,-zve64x,-zvfh,-zvl1024b,-zvl128b,-zvl16384b,-zvl2048b,-zvl256b,-zvl32768b,-zvl32b,-zvl4096b,-zvl512b,-zvl64b,-zvl65536b,-zvl8192b" }

!llvm.module.flags = !{!0, !1, !2}
!llvm.ident = !{!3}

!0 = !{i32 1, !"wchar_size", i32 4}
!1 = !{i32 1, !"target-abi", !"lp64d"}
!2 = !{i32 8, !"SmallDataLimit", i32 8}
!3 = !{!"(built by Brecht Sanders, r4) clang version 17.0.6"}
!4 = distinct !{!4, !5, !6}
!5 = !{!"llvm.loop.mustprogress"}
!6 = !{!"llvm.loop.unroll.disable"}
