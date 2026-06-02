package com.dtp.dtpassist.data.local

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "messages")
data class ChatEntity(
    @PrimaryKey val id: Long,
    val chatId: Long,
    val text: String,
    val isUser: Boolean,
    val createdAt: Long,
)

@Entity(tableName = "chats")
data class ChatThreadEntity(
    @PrimaryKey val id: Long,
    val title: String,
    val createdAt: Long,
)

@Dao
interface ChatDao {
    @Query("SELECT * FROM messages WHERE chatId = :chatId ORDER BY createdAt ASC")
    fun observe(chatId: Long): Flow<List<ChatEntity>>

    @Query("SELECT * FROM chats ORDER BY createdAt DESC")
    fun observeChats(): Flow<List<ChatThreadEntity>>

    @Query("SELECT * FROM chats WHERE id = :chatId LIMIT 1")
    suspend fun getChatById(chatId: Long): ChatThreadEntity?

    @Query("SELECT * FROM chats ORDER BY createdAt DESC LIMIT 1")
    suspend fun getLatestChat(): ChatThreadEntity?

    @Insert
    suspend fun insert(message: ChatEntity)

    @Insert
    suspend fun insertChat(chat: ChatThreadEntity)

    @Query("DELETE FROM messages WHERE chatId = :chatId")
    suspend fun clear(chatId: Long)

    @Query("DELETE FROM chats WHERE id = :chatId")
    suspend fun deleteChat(chatId: Long)

    @Query("DELETE FROM messages")
    suspend fun clearAllMessages()

    @Query("DELETE FROM chats")
    suspend fun clearAllChats()
}

@Database(entities = [ChatEntity::class, ChatThreadEntity::class], version = 2, exportSchema = false)
abstract class ChatDatabase : RoomDatabase() {
    abstract fun chatDao(): ChatDao

    companion object {
        fun create(context: Context) = Room.databaseBuilder(context, ChatDatabase::class.java, "offline_chat.db")
            .fallbackToDestructiveMigration()
            .build()
    }
}
