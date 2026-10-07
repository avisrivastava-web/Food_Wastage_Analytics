# WasteLens Analytics Guide

This guide explains what each major analysis means, what question it answers, and how to use it operationally.

## 1. Executive KPIs

- **Total food waste (kg):** sum of all recorded daily wastage in the selected period.
- **Average waste/day:** average kilograms discarded per recorded day.
- **Median waste/day:** middle daily value; useful because one abnormal day affects it less than the average.
- **Highest-waste day:** the single worst recorded day in the selected period.
- **Flagged dishes:** dishes that cross the configured association-risk threshold and repetition requirement.
- **Data maturity score:** 0–100 readiness score based on matched dates, completeness, cover data and repeated dish observations.

## 2. Dish association-risk score

The system receives one total-waste figure for the entire day, so it cannot prove which exact dish was discarded. It therefore ranks menu items by association.

A dish scores higher when it:

- appears repeatedly,
- occurs on days with higher average waste,
- has positive lift versus days when it is absent,
- appears on many high-waste days,
- has positive correlation with daily waste,
- and has enough observations for stronger confidence.

Use this score to decide what to investigate first, not as proof that the dish caused the waste.

## 3. Weekday benchmark

For every date, WasteLens compares actual waste with the average for the same weekday in the selected period.

- Positive variance = worse than the normal value for that weekday.
- Negative variance = better than the normal value for that weekday.

This is useful because Mondays, weekends or event days may naturally behave differently.

## 4. Attendance and efficiency

When covers served are available, the system calculates:

- **kg per cover** = total waste / covers served,
- correlation between covers and total waste,
- a simple attendance-based expected-waste line,
- and residual/excess waste beyond what attendance alone suggests.

Large positive residuals are useful investigation candidates because they are harder to explain only by higher attendance.

## 5. Process control

WasteLens plots:

- process mean,
- +2 standard deviation warning line,
- +3 standard deviation control line.

A day outside the +3σ limit can indicate a special cause such as a service disruption, quality problem, attendance error or production mistake.

## 6. Menu structure

The system evaluates:

- number of distinct dishes versus waste,
- meal-specific dish counts versus waste,
- menu novelty versus waste,
- repeating dish pairs,
- repeating meal-menu combinations within Breakfast, Lunch, Snacks or Dinner.

These analyses help identify whether the problem may be menu design or menu breadth rather than one specific item.

## 7. Pareto view

Positive excess-waste association is allocated across dishes present on above-baseline days. The chart shows which dishes account for the largest share of this allocated association.

Common dishes with non-positive lift are excluded so frequently served staples do not dominate simply because of repetition.

## 8. Scenario planner

The scenario planner combines:

- historical median waste,
- attendance adjustment,
- positive dish associations.

Dish effects are deliberately dampened to reduce double-counting because dishes often appear together. Treat the result as an indicative planning range, not a guaranteed forecast.

## 9. Financial planning

In the sidebar you can optionally enter a blended food cost per kilogram and a waste-reduction target. WasteLens will then estimate:

- cost represented by recorded waste,
- kilograms to reduce at the selected target,
- indicative savings.

This is not an accounting valuation because ingredient costs vary by dish.

## 10. Data maturity

The 0–100 score uses:

- number of matched menu + wastage days,
- overall date completeness,
- cover-count availability,
- share of dishes repeated at least three times.

Interpretation:

- **0–39 Early:** collect more consistent data.
- **40–59 Developing:** useful for investigation, weak for decisions.
- **60–79 Good:** stronger operational patterns available.
- **80–100 Strong:** good repeated-pattern coverage, while daily-total attribution limits still apply.

## Recommended operating process

1. Record menu, waste, covers and notes every day.
2. Review the Overview weekly.
3. Check attendance-normalized efficiency before blaming the menu.
4. Investigate statistical exceptions and read operational notes.
5. Shortlist only repeated/high-confidence menu signals.
6. Run small controlled production or portion-size changes.
7. Continue recording and compare future results with weekday and attendance benchmarks.


## Dish exclusion filter

The sidebar's **Dish exclusions** control allows one or more dishes to be ignored temporarily in all menu-based analytics. Use it to test sensitivity ("what changes if we ignore this dish?"), to remove a known bad label/data artifact, or to exclude a compulsory staple from prioritization.

**What changes:** dish ranking, dish×meal analysis, Pareto allocation, complexity, novelty, pairs, repeating meal menus, high-waste menu descriptions and scenario-planner dish choices are recalculated from the remaining dishes.

**What does not change:** stored menu records, raw exports and total daily wastage. Because the source data does not contain dish-level wasted kilograms, excluding a dish cannot subtract any specific kg amount from the day's recorded total.

The exclusion list lasts for the active Streamlit session and can be cleared from the same sidebar control.
