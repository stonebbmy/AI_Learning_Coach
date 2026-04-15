
package com.example.aicoach.repository;

import com.example.aicoach.entity.DailyPlan;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.Optional;

/**
 * Spring Data JPA repository for the {@link DailyPlan} entity.
 */
@Repository
public interface DailyPlanRepository extends JpaRepository<DailyPlan, Long> {

    /**
     * Finds a daily plan by its date.
     * @param date the date of the plan
     * @return an Optional containing the plan if found
     */
    Optional<DailyPlan> findByPlanDate(LocalDate date);
}
