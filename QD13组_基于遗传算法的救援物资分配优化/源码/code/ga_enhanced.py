# ==============================================================================
# 遗传算法增强模块
# 改进点：精英保留、全局最优追踪、锦标赛选择、自适应变异、局部搜索
# ==============================================================================

import numpy as np


class GAEnhancedMixin:
    """遗传算法增强算子与优化主循环（供 AllocationModel 继承）"""

    def tournament_select(self, population, fitness_scores, tournament_size=3):
        """锦标赛选择：多次随机抽样取最优"""
        fitness_scores = np.array(fitness_scores)
        valid_indices = np.where(fitness_scores >= 0)[0]

        if len(valid_indices) == 0:
            return population[0], population[min(1, len(population) - 1)]

        def pick_one():
            candidates = np.random.choice(
                valid_indices,
                size=min(tournament_size, len(valid_indices)),
                replace=False,
            )
            best = candidates[np.argmax(fitness_scores[candidates])]
            return population[best]

        return pick_one(), pick_one()

    def crossover_enhanced(self, parent1, parent2, crossover_rate=0.85):
        """增强交叉：按仓库块交换，保留父代优良片段"""
        if np.random.random() > crossover_rate:
            return parent1.copy(), parent2.copy()

        child1 = parent1.copy()
        child2 = parent2.copy()

        # 随机选择若干仓库进行块交换
        swap_count = max(1, int(self.num_warehouses * 0.4))
        swap_warehouses = np.random.choice(self.num_warehouses, swap_count, replace=False)

        for w in swap_warehouses:
            if np.random.random() < 0.5:
                child1[w, :, :] = parent2[w, :, :]
                child2[w, :, :] = parent1[w, :, :]
            else:
                # 按受灾点交换
                p_cross = np.random.randint(self.num_points)
                child1[w, p_cross:, :] = parent2[w, p_cross:, :]
                child2[w, p_cross:, :] = parent1[w, p_cross:, :]

        return child1, child2

    def mutate_adaptive(self, individual, mutation_rate):
        """自适应变异：对紧急程度高且满足率低的分配加大扰动"""
        mutated = individual.copy()
        received = np.sum(mutated, axis=0)
        satisfaction = np.minimum(received / (self.demand + 1e-10), 1.0)
        point_deficit = 1.0 - np.mean(satisfaction, axis=1)

        for w in range(self.num_warehouses):
            for p in range(self.num_points):
                # 紧急且缺口大的点更容易变异
                urgency_factor = float(self.urgency_weights[p]) if hasattr(self, 'urgency_weights') else 1.0
                deficit_factor = float(point_deficit[p])
                local_rate = min(0.5, mutation_rate * (1.0 + urgency_factor * 3 + deficit_factor * 2))

                for m in range(self.num_materials):
                    if np.random.random() < local_rate:
                        max_possible = min(
                            self.inventory[w, m] - np.sum(mutated[w, :, m]) + mutated[w, p, m],
                            self.demand[p, m] - np.sum(mutated[:, p, m]) + mutated[w, p, m],
                        )
                        if max_possible > 0:
                            # 偏向增加分配（提升满足率）
                            if np.random.random() < 0.7:
                                mutated[w, p, m] = min(
                                    max_possible,
                                    mutated[w, p, m] + np.random.uniform(0, max_possible * 0.3),
                                )
                            else:
                                mutated[w, p, m] = np.random.uniform(0, max_possible)

        return mutated

    def local_search(self, individual, steps=5):
        """贪心局部搜索：在可行域内尝试小幅调拨以提升适应度"""
        best = individual.copy()
        best_fitness = self.fitness(best)
        if best_fitness < 0:
            return self.repair(best)

        received = np.sum(best, axis=0)
        satisfaction = np.minimum(received / (self.demand + 1e-10), 1.0)
        point_scores = np.mean(satisfaction, axis=1)

        for _ in range(steps):
            # 从满足率较高的点向满足率较低的点调拨
            p_from = int(np.argmax(point_scores))
            p_to = int(np.argmin(point_scores))
            if p_from == p_to:
                break

            w = np.random.randint(self.num_warehouses)
            m = np.random.randint(self.num_materials)

            if best[w, p_from, m] <= 0:
                continue

            max_shift = min(
                best[w, p_from, m] * 0.15,
                self.demand[p_to, m] - np.sum(best[:, p_to, m]),
                self.max_transport_capacity(w) - np.sum(best[w, :, :]) + np.sum(best[w, p_from, :]),
            )
            if max_shift <= 1e-6:
                continue

            candidate = best.copy()
            shift = max_shift * np.random.uniform(0.3, 1.0)
            candidate[w, p_from, m] -= shift
            candidate[w, p_to, m] += shift
            candidate = self.repair(candidate)

            candidate_fitness = self.fitness(candidate)
            if candidate_fitness > best_fitness:
                best = candidate
                best_fitness = candidate_fitness
                received = np.sum(best, axis=0)
                satisfaction = np.minimum(received / (self.demand + 1e-10), 1.0)
                point_scores = np.mean(satisfaction, axis=1)

        return best

    def _get_elite_indices(self, fitness_scores, elite_count):
        """获取精英个体索引"""
        fitness_scores = np.array(fitness_scores)
        valid_mask = fitness_scores >= 0
        if not np.any(valid_mask):
            return [0]

        valid_indices = np.where(valid_mask)[0]
        sorted_valid = valid_indices[np.argsort(fitness_scores[valid_indices])[::-1]]
        return sorted_valid[:max(1, elite_count)].tolist()

    def optimize_enhanced(
        self,
        pop_size=100,
        generations=50,
        mutation_rate=0.1,
        elite_ratio=0.1,
        crossover_rate=0.85,
        tournament_size=3,
        local_search_steps=4,
        stagnation_patience=6,
    ):
        """
        增强版遗传算法优化主循环

        特性：
        - 全局最优个体始终保留（适应度曲线单调不降）
        - 锦标赛选择 + 自适应变异 + 局部搜索
        - 停滞时自动提高变异率以跳出局部最优
        """
        population = self.generate_population(pop_size)

        # 对初始种群中前几个个体做局部搜索，提高起点质量
        seed_count = min(5, pop_size)
        for i in range(seed_count):
            population[i] = self.local_search(population[i], steps=local_search_steps)

        fitness_scores = [self.fitness(ind) for ind in population]
        best_idx = int(np.argmax(fitness_scores))
        best_ever = population[best_idx].copy()
        best_ever_fitness = fitness_scores[best_idx]

        fitness_history = [best_ever_fitness]
        stagnation = 0
        current_mutation = mutation_rate
        elite_count = max(1, int(pop_size * elite_ratio))

        for gen in range(generations):
            # 精英保留
            elite_indices = self._get_elite_indices(fitness_scores, elite_count)
            new_population = [population[i].copy() for i in elite_indices]
            new_population[0] = best_ever.copy()

            # 生成新个体
            while len(new_population) < pop_size:
                parent1, parent2 = self.tournament_select(
                    population, fitness_scores, tournament_size
                )
                child1, child2 = self.crossover_enhanced(
                    parent1, parent2, crossover_rate
                )

                child1 = self.mutate_adaptive(child1, current_mutation)
                child2 = self.mutate_adaptive(child2, current_mutation)

                child1 = self.repair(child1)
                child2 = self.repair(child2)

                child1 = self.local_search(child1, steps=local_search_steps)
                child2 = self.local_search(child2, steps=local_search_steps)

                new_population.extend([child1, child2])

            population = new_population[:pop_size]
            fitness_scores = [self.fitness(ind) for ind in population]

            gen_best_idx = int(np.argmax(fitness_scores))
            gen_best_fitness = fitness_scores[gen_best_idx]

            if gen_best_fitness > best_ever_fitness + 1e-10:
                best_ever = population[gen_best_idx].copy()
                best_ever_fitness = gen_best_fitness
                stagnation = 0
                current_mutation = mutation_rate
            else:
                stagnation += 1
                if stagnation >= stagnation_patience:
                    current_mutation = min(0.35, mutation_rate * 1.8)
                    stagnation = 0
                else:
                    current_mutation = max(mutation_rate * 0.5, mutation_rate * (1 - stagnation * 0.05))

            # 历史记录使用全局最优，保证曲线单调不降
            fitness_history.append(best_ever_fitness)

            if (gen + 1) % 10 == 0:
                valid = [f for f in fitness_scores if f >= 0]
                avg_fit = np.mean(valid) if valid else 0.0
                print(
                    f"第 {gen + 1} 代: 最优适应度 = {best_ever_fitness:.4f}, "
                    f"当代平均 = {avg_fit:.4f}, 变异率 = {current_mutation:.3f}"
                )

        return best_ever, fitness_history
