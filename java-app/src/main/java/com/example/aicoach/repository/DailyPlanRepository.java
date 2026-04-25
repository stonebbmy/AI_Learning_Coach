
package com.example.aicoach.repository;

import com.example.aicoach.entity.DailyPlan;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * Spring Data JPA repository for the {@link DailyPlan} entity.
 */
@Repository
public interface DailyPlanRepository extends JpaRepository<DailyPlan, Long> {

    Optional<DailyPlan> findByPlanDate(LocalDate date);

    Optional<DailyPlan> findByPlanDateAndUserId(LocalDate date, String userId);

    List<DailyPlan> findByUserIdOrderByPlanDateDesc(String userId);

    @Modifying
    @Query("update DailyPlan d set d.sourceOutlineId = null where d.sourceOutlineId = :outlineId")
    int clearSourceOutlineIdByOutlineId(@Param("outlineId") Long outlineId);
}
