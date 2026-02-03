import {
  Task,
  TymeboxRecommendation,
  DecisionAgentContext,
  TymeboxOutcome,
} from "../types";

// Decision Agent 接口
export interface IDecisionAgent {
  recommend(context: DecisionAgentContext): Promise<TymeboxRecommendation>;
}

/**
 * API Decision Agent Implementation
 * Connects to the backend to get recommendations
 */
export class APIDecisionAgent implements IDecisionAgent {
  async recommend(
    context: DecisionAgentContext
  ): Promise<TymeboxRecommendation> {
    // Backend recommendation endpoint is not available yet.
    return new DefaultDecisionAgent().recommend(context);
  }
}

/**
 * 默认 Decision Agent 实现 (Fallback)
 */
export class DefaultDecisionAgent implements IDecisionAgent {
  async recommend(
    context: DecisionAgentContext
  ): Promise<TymeboxRecommendation> {
    const { tasks, outcomes, preferLowCognitiveLoad } = context;

    if (tasks.length === 0) {
      // 没有任务，返回空推荐
      // throw new Error("No tasks available for recommendation");
       return {
          taskId: "dummy",
          durationMinutes: 15,
          reason: "No tasks available locally",
          preferLowCognitiveLoad: !!preferLowCognitiveLoad
      };
    }

    // 过滤出可用任务
    const availableTasks = this.filterAvailableTasks(tasks, outcomes);

    if (availableTasks.length === 0) {
      // 所有任务都完成了，从原始任务池中选择
      return this.selectTask(tasks, preferLowCognitiveLoad);
    }

    return this.selectTask(availableTasks, preferLowCognitiveLoad);
  }

  private filterAvailableTasks(
    tasks: Task[],
    outcomes: TymeboxOutcome[]
  ): Task[] {
    const completedTaskIds = new Set(
      outcomes
        .filter((o) => o.outcome === "completed")
        .map((o) => o.taskId)
    );

    return tasks.filter((task) => !completedTaskIds.has(task.id));
  }

  private selectTask(
    tasks: Task[],
    preferLowCognitiveLoad?: boolean
  ): TymeboxRecommendation {
    let selectedTask: Task;
    let reason: string;

    if (preferLowCognitiveLoad) {
      // 中断后，优先选择低认知负荷的任务
      const lowCogTasks = tasks.filter(
        (t) => t.cognitiveLoad === "low" || t.priority === "low"
      );
      selectedTask = lowCogTasks.length > 0 ? lowCogTasks[0] : tasks[0];
      reason = "Recommended low cognitive load task after interruption";
    } else {
      // 正常情况，按优先级排序
      const sortedTasks = this.sortByPriority(tasks);
      selectedTask = sortedTasks[0];
      reason = this.getReasonByPriority(selectedTask.priority);
    }

    const durationMinutes = this.suggestDuration(selectedTask);

    return {
      taskId: selectedTask.id,
      durationMinutes,
      reason,
      preferLowCognitiveLoad,
    };
  }

  private sortByPriority(tasks: Task[]): Task[] {
    const priorityOrder = { urgent: 0, medium: 1, low: 2 };
    return [...tasks].sort(
      (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]
    );
  }

  private suggestDuration(task: Task): number {
    if (task.estimatedMinutes) {
      return Math.min(task.estimatedMinutes, 45);
    }
    if (task.cognitiveLoad === "high" || task.priority === "urgent") {
      return 25;
    } else if (task.cognitiveLoad === "low" || task.priority === "low") {
      return 15;
    }
    return 25;
  }

  private getReasonByPriority(
    priority: "urgent" | "medium" | "low"
  ): string {
    switch (priority) {
      case "urgent":
        return "High priority task requiring immediate attention";
      case "medium":
        return "Regular priority task for steady progress";
      case "low":
        return "Light task suitable for maintaining momentum";
      default:
        return "Recommended based on current context";
    }
  }
}

// Export API Agent as default
export const decisionAgent: IDecisionAgent = new APIDecisionAgent();
