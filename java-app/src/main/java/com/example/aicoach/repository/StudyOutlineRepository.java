
package com.example.aicoach.repository;

import com.example.aicoach.entity.StudyOutline;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for the {@link StudyOutline} entity.
 */
@Repository
public interface StudyOutlineRepository extends JpaRepository<StudyOutline, Long> {
}
