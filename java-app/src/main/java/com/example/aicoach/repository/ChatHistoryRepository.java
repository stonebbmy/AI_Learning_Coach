
package com.example.aicoach.repository;

import com.example.aicoach.entity.ChatHistory;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for the {@link ChatHistory} entity.
 */
@Repository
public interface ChatHistoryRepository extends JpaRepository<ChatHistory, Long> {
}
