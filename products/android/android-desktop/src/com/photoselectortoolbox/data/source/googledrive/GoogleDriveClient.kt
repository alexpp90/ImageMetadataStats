package com.photoselectortoolbox.data.source.googledrive

import android.util.Log
import java.io.File
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Lightweight data class for a Drive file/folder entry. */
data class DriveFile(
    val id: String,
    val name: String,
    val mimeType: String,
    val size: Long = 0,
    val modifiedTime: Long = 0,
    val thumbnailLink: String? = null,
    val imageWidth: Int = 0,
    val imageHeight: Int = 0,
) {
    val isFolder: Boolean get() = mimeType == MIME_FOLDER

    companion object {
        const val MIME_FOLDER = "application/vnd.google-apps.folder"
    }
}

/**
 * Lightweight Google Drive REST API v3 client.
 * Uses raw HttpURLConnection — no extra library dependencies.
 */
@Singleton
class GoogleDriveClient @Inject constructor(
    private val auth: GoogleDriveAuth,
) {
    companion object {
        private const val TAG = "GoogleDriveClient"
        private const val BASE_URL = "https://www.googleapis.com/drive/v3"
        private const val UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3"
        private const val PAGE_SIZE = 200

        /** Image MIME types the app supports. */
        val IMAGE_MIME_TYPES = listOf(
            "image/jpeg", "image/png", "image/tiff", "image/bmp", "image/gif",
            "image/webp", "image/heif", "image/heic", "image/x-adobe-dng",
            "image/x-canon-cr2", "image/x-canon-cr3", "image/x-nikon-nef",
            "image/x-sony-arw", "image/x-olympus-orf", "image/x-panasonic-rw2",
            "image/x-pentax-pef", "image/x-samsung-srw", "image/x-fuji-raf",
        )
    }

    /**
     * List image files in a Drive folder. Returns all images recursively
     * if [recursive] is true, otherwise just direct children.
     */
    suspend fun listImages(
        folderId: String,
        recursive: Boolean = true,
    ): List<DriveFile> = withContext(Dispatchers.IO) {
        val results = mutableListOf<DriveFile>()
        listImagesInternal(folderId, recursive, results)
        results.sortedBy { it.name.lowercase() }
    }

    private suspend fun listImagesInternal(
        folderId: String,
        recursive: Boolean,
        results: MutableList<DriveFile>,
    ) {
        var pageToken: String? = null
        do {
            // Query for images, generic octet-streams, and folders (to recurse into)
            val mimeFilter = (IMAGE_MIME_TYPES + "application/octet-stream").joinToString(" or ") { "mimeType='$it'" }
            val query = "'$folderId' in parents and trashed=false and ($mimeFilter or mimeType='${DriveFile.MIME_FOLDER}')"
            val fields = "nextPageToken,files(id,name,mimeType,size,modifiedTime,imageMediaMetadata/width,imageMediaMetadata/height)"

            val url = buildString {
                append("$BASE_URL/files?")
                append("q=${URLEncoder.encode(query, "UTF-8")}")
                append("&fields=${URLEncoder.encode(fields, "UTF-8")}")
                append("&pageSize=$PAGE_SIZE")
                append("&orderBy=name")
                if (pageToken != null) append("&pageToken=$pageToken")
            }

            val json = httpGet(url) ?: break

            val files = json.optJSONArray("files") ?: break
            for (i in 0 until files.length()) {
                val f = files.getJSONObject(i)
                val mime = f.getString("mimeType")

                if (mime == DriveFile.MIME_FOLDER) {
                    // Skip "Selection" / "Selected" folders just like the local source
                    val folderName = f.getString("name").lowercase()
                    if (folderName == "selection" || folderName == "selected") continue

                    if (recursive) {
                        listImagesInternal(f.getString("id"), true, results)
                    }
                } else {
                    val meta = f.optJSONObject("imageMediaMetadata")
                    results.add(
                        DriveFile(
                            id = f.getString("id"),
                            name = f.getString("name"),
                            mimeType = mime,
                            size = f.optLong("size", 0),
                            modifiedTime = parseRfc3339(f.optString("modifiedTime", "")),
                            imageWidth = meta?.optInt("width", 0) ?: 0,
                            imageHeight = meta?.optInt("height", 0) ?: 0,
                        )
                    )
                }
            }

            pageToken = json.optString("nextPageToken", null)
        } while (!pageToken.isNullOrEmpty())
    }

    /** List only folders inside a given parent (for the folder picker). */
    suspend fun listFolders(parentId: String): List<DriveFile> = withContext(Dispatchers.IO) {
        val results = mutableListOf<DriveFile>()
        var pageToken: String? = null
        do {
            val query = "'$parentId' in parents and mimeType='${DriveFile.MIME_FOLDER}' and trashed=false"
            val fields = "nextPageToken,files(id,name,mimeType)"

            val url = buildString {
                append("$BASE_URL/files?")
                append("q=${URLEncoder.encode(query, "UTF-8")}")
                append("&fields=${URLEncoder.encode(fields, "UTF-8")}")
                append("&pageSize=$PAGE_SIZE")
                append("&orderBy=name")
                if (pageToken != null) append("&pageToken=$pageToken")
            }

            val json = httpGet(url) ?: break
            val files = json.optJSONArray("files") ?: break
            for (i in 0 until files.length()) {
                val f = files.getJSONObject(i)
                results.add(
                    DriveFile(
                        id = f.getString("id"),
                        name = f.getString("name"),
                        mimeType = f.getString("mimeType"),
                    )
                )
            }
            pageToken = json.optString("nextPageToken", null)
        } while (!pageToken.isNullOrEmpty())
        results
    }

    /** Download a Drive file to a local cache file. Returns the local path or null. */
    suspend fun downloadFile(fileId: String, destFile: File): Boolean = withContext(Dispatchers.IO) {
        try {
            val token = auth.getAccessToken() ?: return@withContext false
            val url = URL("$BASE_URL/files/$fileId?alt=media")
            val conn = url.openConnection() as HttpURLConnection
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.connectTimeout = 30_000
            conn.readTimeout = 60_000

            if (conn.responseCode == HttpURLConnection.HTTP_OK) {
                destFile.parentFile?.mkdirs()
                conn.inputStream.use { input ->
                    destFile.outputStream().use { output ->
                        input.copyTo(output, bufferSize = 8192)
                    }
                }
                true
            } else {
                Log.e(TAG, "Download failed: ${conn.responseCode} ${conn.responseMessage}")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Download error for $fileId", e)
            false
        }
    }

    /**
     * Upload a file to a Drive folder. Uses simple upload for files under 5MB,
     * otherwise uses resumable upload.
     */
    suspend fun uploadFile(
        parentFolderId: String,
        fileName: String,
        mimeType: String,
        inputFile: File,
    ): String? = withContext(Dispatchers.IO) {
        try {
            val token = auth.getAccessToken() ?: return@withContext null

            // Multipart upload (metadata + content)
            val boundary = "====${System.currentTimeMillis()}===="
            val metadata = JSONObject().apply {
                put("name", fileName)
                put("parents", org.json.JSONArray().put(parentFolderId))
            }

            val url = URL("$UPLOAD_URL/files?uploadType=multipart")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Content-Type", "multipart/related; boundary=$boundary")

            conn.outputStream.use { out ->
                writeMultipartBody(out, boundary, metadata.toString(), mimeType, inputFile)
            }

            if (conn.responseCode in 200..299) {
                val response = conn.inputStream.bufferedReader().readText()
                val json = JSONObject(response)
                json.getString("id")
            } else {
                Log.e(TAG, "Upload failed: ${conn.responseCode}")
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "Upload error", e)
            null
        }
    }

    /** Create a folder inside a parent folder. Returns the new folder's ID. */
    suspend fun createFolder(parentId: String, folderName: String): String? =
        withContext(Dispatchers.IO) {
            try {
                val token = auth.getAccessToken() ?: return@withContext null
                val metadata = JSONObject().apply {
                    put("name", folderName)
                    put("mimeType", DriveFile.MIME_FOLDER)
                    put("parents", org.json.JSONArray().put(parentId))
                }

                val url = URL("$BASE_URL/files")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.setRequestProperty("Content-Type", "application/json")

                conn.outputStream.use { out ->
                    out.write(metadata.toString().toByteArray())
                }

                if (conn.responseCode in 200..299) {
                    val response = conn.inputStream.bufferedReader().readText()
                    JSONObject(response).getString("id")
                } else {
                    Log.e(TAG, "Create folder failed: ${conn.responseCode}")
                    null
                }
            } catch (e: Exception) {
                Log.e(TAG, "Create folder error", e)
                null
            }
        }

    /** Find or create a subfolder by name inside a parent. */
    suspend fun findOrCreateFolder(parentId: String, folderName: String): String? =
        withContext(Dispatchers.IO) {
            // Search for existing
            val query = "'$parentId' in parents and mimeType='${DriveFile.MIME_FOLDER}' and name='$folderName' and trashed=false"
            val fields = "files(id)"
            val url = buildString {
                append("$BASE_URL/files?")
                append("q=${URLEncoder.encode(query, "UTF-8")}")
                append("&fields=${URLEncoder.encode(fields, "UTF-8")}")
                append("&pageSize=1")
            }
            val json = httpGet(url)
            val files = json?.optJSONArray("files")
            if (files != null && files.length() > 0) {
                return@withContext files.getJSONObject(0).getString("id")
            }
            // Create new
            createFolder(parentId, folderName)
        }

    /** Delete a file from Drive (move to trash). */
    suspend fun trashFile(fileId: String): Boolean = setTrashed(fileId, trashed = true)

    /**
     * Bring a trashed file back out of the Drive trash.
     *
     * The inverse of [trashFile] and the reason a Drive delete can offer a real
     * UNDO where a SAF delete cannot: same endpoint, same scope, one flag
     * flipped — no additional data leaves the device.
     */
    suspend fun untrashFile(fileId: String): Boolean = setTrashed(fileId, trashed = false)

    private suspend fun setTrashed(fileId: String, trashed: Boolean): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val token = auth.getAccessToken() ?: return@withContext false
                val body = JSONObject().apply { put("trashed", trashed) }

                val url = URL("$BASE_URL/files/$fileId")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "PATCH"
                conn.doOutput = true
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.setRequestProperty("Content-Type", "application/json")

                conn.outputStream.use { it.write(body.toString().toByteArray()) }
                conn.responseCode in 200..299
            } catch (e: Exception) {
                Log.e(TAG, "Setting trashed=$trashed failed for $fileId", e)
                false
            }
        }

    /** Copy a file to a different folder on Drive. Returns the new file's ID. */
    suspend fun copyFile(fileId: String, destFolderId: String, newName: String? = null): String? =
        withContext(Dispatchers.IO) {
            try {
                val token = auth.getAccessToken() ?: return@withContext null
                val metadata = JSONObject().apply {
                    put("parents", org.json.JSONArray().put(destFolderId))
                    if (newName != null) put("name", newName)
                }

                val url = URL("$BASE_URL/files/$fileId/copy")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.setRequestProperty("Content-Type", "application/json")

                conn.outputStream.use { it.write(metadata.toString().toByteArray()) }

                if (conn.responseCode in 200..299) {
                    val response = conn.inputStream.bufferedReader().readText()
                    JSONObject(response).getString("id")
                } else {
                    Log.e(TAG, "Copy failed: ${conn.responseCode}")
                    null
                }
            } catch (e: Exception) {
                Log.e(TAG, "Copy error", e)
                null
            }
        }

    /**
     * The folders this file currently lives in.
     *
     * Returns `null` when the answer could not be obtained — no token, a
     * transport error, an HTTP failure — and an **empty list** when the request
     * succeeded and the file genuinely has no parent (an orphan, or a
     * shared-with-me file that was never added to a folder). The caller must
     * distinguish the two: "I do not know the parents" and "there are none" lead
     * to opposite decisions in [moveFile].
     *
     * `files.get` with `fields=parents` is the same endpoint family and the same
     * OAuth scope as the metadata reads discovery already performs, and asking
     * for a field sends nothing additional off the device.
     */
    suspend fun parentsOf(fileId: String): List<String>? = withContext(Dispatchers.IO) {
        val url = "$BASE_URL/files/$fileId?fields=${URLEncoder.encode("parents", "UTF-8")}"
        val json = httpGet(url) ?: return@withContext null
        val parents = json.optJSONArray("parents") ?: return@withContext emptyList()
        (0 until parents.length())
            .mapNotNull { i -> parents.optString(i).takeIf { it.isNotEmpty() } }
    }

    /**
     * Move a file: add [newParentId], remove every folder in [removeParentIds].
     *
     * [removeParentIds] is a collection and not a single id on purpose. It used
     * to be one `oldParentId`, and the one call site passed the *destination*
     * folder — so Drive removed a parent the file did not have and the "move"
     * added a second parent instead of relocating the file, leaving the
     * photograph in the source folder after the selector had already taken it
     * off the list. Drive files may legitimately have several parents (legacy
     * multi-parenting), so the caller resolves them with [parentsOf] and passes
     * all of them; a signature that can only express one parent is a signature
     * that invites the same bug back.
     *
     * [newParentId] is filtered out of the removals: Drive rejects a PATCH that
     * both adds and removes the same parent.
     */
    suspend fun moveFile(
        fileId: String,
        removeParentIds: Collection<String>,
        newParentId: String,
    ): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val token = auth.getAccessToken() ?: return@withContext false
                val toRemove = removeParentIds.filter { it.isNotEmpty() && it != newParentId }
                val url = URL(
                    buildString {
                        append("$BASE_URL/files/$fileId?addParents=$newParentId")
                        if (toRemove.isNotEmpty()) {
                            // Each id is encoded on its own and the separators
                            // are left literal: `removeParents` is a
                            // comma-separated list, so an encoded comma would
                            // read as one impossible id rather than several.
                            append("&removeParents=")
                            append(toRemove.joinToString(",") { URLEncoder.encode(it, "UTF-8") })
                        }
                    }
                )
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "PATCH"
                conn.setRequestProperty("Authorization", "Bearer $token")
                conn.setRequestProperty("Content-Type", "application/json")
                // Empty body required for PATCH
                conn.doOutput = true
                conn.outputStream.use { it.write("{}".toByteArray()) }

                conn.responseCode in 200..299
            } catch (e: Exception) {
                Log.e(TAG, "Move error", e)
                false
            }
        }

    // ── Internal helpers ─────────────────────────────────────────────────

    private suspend fun httpGet(urlString: String): JSONObject? {
        val token = auth.getAccessToken() ?: return null
        return try {
            val conn = URL(urlString).openConnection() as HttpURLConnection
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.connectTimeout = 15_000
            conn.readTimeout = 30_000

            if (conn.responseCode == HttpURLConnection.HTTP_OK) {
                val body = conn.inputStream.bufferedReader().readText()
                JSONObject(body)
            } else {
                val errorBody = conn.errorStream?.bufferedReader()?.use { it.readText() }
                Log.e(TAG, "HTTP ${conn.responseCode}: ${conn.responseMessage} - Body: $errorBody")
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "HTTP GET failed: $urlString", e)
            null
        }
    }

    private fun writeMultipartBody(
        out: OutputStream,
        boundary: String,
        metadataJson: String,
        contentMimeType: String,
        file: File,
    ) {
        val writer = out.bufferedWriter()

        // Part 1: metadata
        writer.write("--$boundary\r\n")
        writer.write("Content-Type: application/json; charset=UTF-8\r\n\r\n")
        writer.write(metadataJson)
        writer.write("\r\n")

        // Part 2: file content
        writer.write("--$boundary\r\n")
        writer.write("Content-Type: $contentMimeType\r\n\r\n")
        writer.flush()
        file.inputStream().use { it.copyTo(out, bufferSize = 8192) }
        out.flush()
        writer.write("\r\n--$boundary--\r\n")
        writer.flush()
    }

    private fun parseRfc3339(dateString: String): Long {
        if (dateString.isEmpty()) return 0
        return try {
            java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", java.util.Locale.US)
                .apply { timeZone = java.util.TimeZone.getTimeZone("UTC") }
                .parse(dateString)?.time ?: 0
        } catch (_: Exception) {
            try {
                java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US)
                    .apply { timeZone = java.util.TimeZone.getTimeZone("UTC") }
                    .parse(dateString)?.time ?: 0
            } catch (_: Exception) { 0 }
        }
    }
}
