package kz.digitouch.posters

import android.annotation.SuppressLint
import android.content.Context
import android.provider.Settings
import android.util.Log
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * Система лицензирования для Android — порт licensing.py.
 *
 * Формат ключа, секрет HMAC, схема шифрования license.dat — полностью совпадают
 * с Windows-версией. Поэтому один и тот же ключ работает на обеих платформах
 * (но активируется отдельно — лицензия привязывается к устройству).
 */
object Licensing {

    private const val TAG = "Licensing"
    private const val LICENSE_FILENAME = "license.dat"
    private const val ENC_SALT = "interactive-posters-license-v2"
    private const val PBKDF2_ITERATIONS = 100_000
    private const val MAX_CLOCK_DRIFT_HOURS = 24
    private const val LICENSE_VERSION = 2

    // ─── Обфусцированный секрет (XOR _MASK ^ _KDATA) ────────────────
    // Должен быть идентичен licensing.py (генерируется python keygen.py embed)
    private val MASK = intArrayOf(
        0, 4, 51, 226, 213, 62, 45, 201, 14, 126, 242, 86, 239, 239, 194, 85,
        33, 129, 246, 245, 37, 190, 237, 248, 147, 87, 202, 192, 203, 201, 17, 91
    )
    private val KDATA = intArrayOf(
        89, 136, 108, 16, 86, 143, 66, 45, 110, 88, 175, 143, 29, 158, 55, 107,
        170, 111, 116, 154, 64, 224, 210, 220, 4, 150, 168, 123, 166, 18, 231, 195
    )

    private fun getSecret(): ByteArray =
        ByteArray(MASK.size) { i -> ((MASK[i] xor KDATA[i]) and 0xFF).toByte() }

    // ─── Маппинг предметов ──────────────────────────────────────────
    private val SUBJECTS_REV = mapOf(
        0 to "physics", 1 to "mathematics", 2 to "biology", 3 to "chemistry",
        4 to "geography", 5 to "informatics", 6 to "historykaz", 7 to "worldhistory",
        8 to "kazakhlang", 9 to "russianlang", 10 to "englishlang"
    )

    // ─── Результат валидации ────────────────────────────────────────
    data class KeyPayload(
        val subjectIdx: Int,
        val subject: String,
        val clientId: Int,
        val durationMonths: Int,
        val flags: Int
    )

    data class LicenseStatus(
        val valid: Boolean,
        val reason: String,
        val subject: String? = null,
        val expiresAt: String? = null,
        val daysLeft: Int? = null
    )

    // ─── Device ID ──────────────────────────────────────────────────

    @SuppressLint("HardwareIds")
    fun getDeviceId(context: Context): String {
        val raw = try {
            Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ANDROID_ID
            ) ?: ""
        } catch (e: Exception) {
            ""
        }
        val source = raw.ifBlank {
            "fallback-${android.os.Build.MANUFACTURER}-${android.os.Build.MODEL}-${android.os.Build.SERIAL}"
        }
        val sha256 = MessageDigest.getInstance("SHA-256").digest(source.toByteArray(Charsets.UTF_8))
        return sha256.joinToString("") { "%02X".format(it) }.substring(0, 16)
    }

    // ─── Base32 (RFC 4648, без padding) ─────────────────────────────

    private const val BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    private fun base32Decode(input: String): ByteArray? {
        val clean = input.uppercase().filter { it in BASE32_ALPHABET }
        val bits = StringBuilder()
        for (c in clean) {
            val v = BASE32_ALPHABET.indexOf(c)
            if (v < 0) return null
            bits.append(v.toString(2).padStart(5, '0'))
        }
        val out = ByteArray(bits.length / 8)
        for (i in out.indices) {
            out[i] = bits.substring(i * 8, i * 8 + 8).toInt(2).toByte()
        }
        return out
    }

    // ─── HMAC-SHA256 ────────────────────────────────────────────────

    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal(data)
    }

    // ─── Валидация ключа (HMAC) ─────────────────────────────────────

    /**
     * Возвращает payload или null. На Pair.second — текст ошибки если null.
     * HMAC проверяется с учётом device_id → ключ валиден ТОЛЬКО на целевом устройстве.
     */
    fun validateKey(keyStr: String, context: Context): Pair<KeyPayload?, String> {
        val clean = keyStr.replace("-", "").replace(" ", "").uppercase()
        if (clean.length != 20) return null to "Неверный формат ключа"

        val raw = base32Decode(clean) ?: return null to "Неверные символы в ключе"
        if (raw.size != 12) return null to "Неверный формат ключа"

        val payload = raw.copyOfRange(0, 4)
        val sig = raw.copyOfRange(4, 12)
        // HMAC подписывает payload + device_id → ключ привязан к устройству
        val deviceId = getDeviceId(context)
        val hmacData = payload + deviceId.toByteArray(Charsets.UTF_8)
        val expected = hmacSha256(getSecret(), hmacData).copyOfRange(0, 8)

        // Сравнение в постоянном времени
        var diff = 0
        for (i in sig.indices) diff = diff or (sig[i].toInt() xor expected[i].toInt())
        if (diff != 0) return null to "Ключ не подходит для этого устройства"

        val v = ((payload[0].toInt() and 0xFF) shl 24) or
                ((payload[1].toInt() and 0xFF) shl 16) or
                ((payload[2].toInt() and 0xFF) shl 8) or
                (payload[3].toInt() and 0xFF)

        val subjectIdx = (v ushr 28) and 0xF
        val clientId = (v ushr 12) and 0xFFFF
        val durationMonths = (v ushr 4) and 0xFF
        val flags = v and 0xF
        val subject = SUBJECTS_REV[subjectIdx] ?: "unknown"

        return KeyPayload(subjectIdx, subject, clientId, durationMonths, flags) to ""
    }

    // ─── PBKDF2-HMAC-SHA256 (ручная реализация для совместимости) ───

    private fun pbkdf2HmacSha256(
        password: ByteArray,
        salt: ByteArray,
        iterations: Int,
        dkLen: Int
    ): ByteArray {
        val hLen = 32  // SHA-256
        val blocks = (dkLen + hLen - 1) / hLen
        val out = ByteArray(dkLen)
        var outOffset = 0
        for (i in 1..blocks) {
            // U1 = PRF(password, salt || INT_32_BE(i))
            val saltInt = ByteArray(salt.size + 4)
            System.arraycopy(salt, 0, saltInt, 0, salt.size)
            saltInt[salt.size]     = ((i ushr 24) and 0xFF).toByte()
            saltInt[salt.size + 1] = ((i ushr 16) and 0xFF).toByte()
            saltInt[salt.size + 2] = ((i ushr 8) and 0xFF).toByte()
            saltInt[salt.size + 3] = (i and 0xFF).toByte()

            var u = hmacSha256(password, saltInt)
            val t = u.copyOf()
            for (c in 2..iterations) {
                u = hmacSha256(password, u)
                for (k in t.indices) t[k] = (t[k].toInt() xor u[k].toInt()).toByte()
            }
            val toCopy = minOf(hLen, dkLen - outOffset)
            System.arraycopy(t, 0, out, outOffset, toCopy)
            outOffset += toCopy
        }
        return out
    }

    private fun deriveEncKey(deviceId: String): ByteArray =
        pbkdf2HmacSha256(
            deviceId.toByteArray(Charsets.UTF_8),
            ENC_SALT.toByteArray(Charsets.UTF_8),
            PBKDF2_ITERATIONS,
            32
        )

    // ─── Шифрование (HMAC-keystream XOR + integrity tag) ────────────

    private fun encryptLicense(data: JSONObject, deviceId: String): ByteArray {
        val key = deriveEncKey(deviceId)
        val plaintext = data.toString().toByteArray(Charsets.UTF_8)
        val ciphertext = ByteArray(plaintext.size)

        var offset = 0
        var counter = 0
        while (offset < plaintext.size) {
            val counterBytes = byteArrayOf(
                ((counter ushr 24) and 0xFF).toByte(),
                ((counter ushr 16) and 0xFF).toByte(),
                ((counter ushr 8) and 0xFF).toByte(),
                (counter and 0xFF).toByte()
            )
            val blockKey = hmacSha256(key, counterBytes)
            val end = minOf(offset + 32, plaintext.size)
            for (j in offset until end) {
                ciphertext[j] = (plaintext[j].toInt() xor blockKey[j - offset].toInt()).toByte()
            }
            offset += 32
            counter += 1
        }

        val tag = hmacSha256(key, ciphertext).copyOfRange(0, 16)
        val out = ByteArray(16 + ciphertext.size)
        System.arraycopy(tag, 0, out, 0, 16)
        System.arraycopy(ciphertext, 0, out, 16, ciphertext.size)
        return out
    }

    private fun decryptLicense(raw: ByteArray, deviceId: String): JSONObject? {
        if (raw.size < 17) return null
        val key = deriveEncKey(deviceId)
        val tag = raw.copyOfRange(0, 16)
        val ciphertext = raw.copyOfRange(16, raw.size)

        val expectedTag = hmacSha256(key, ciphertext).copyOfRange(0, 16)
        var diff = 0
        for (i in tag.indices) diff = diff or (tag[i].toInt() xor expectedTag[i].toInt())
        if (diff != 0) return null

        val plaintext = ByteArray(ciphertext.size)
        var offset = 0
        var counter = 0
        while (offset < ciphertext.size) {
            val counterBytes = byteArrayOf(
                ((counter ushr 24) and 0xFF).toByte(),
                ((counter ushr 16) and 0xFF).toByte(),
                ((counter ushr 8) and 0xFF).toByte(),
                (counter and 0xFF).toByte()
            )
            val blockKey = hmacSha256(key, counterBytes)
            val end = minOf(offset + 32, ciphertext.size)
            for (j in offset until end) {
                plaintext[j] = (ciphertext[j].toInt() xor blockKey[j - offset].toInt()).toByte()
            }
            offset += 32
            counter += 1
        }

        return try {
            JSONObject(String(plaintext, Charsets.UTF_8))
        } catch (e: Exception) {
            null
        }
    }

    // ─── Утилиты даты ────────────────────────────────────────────────
    // Python isoformat(timespec='seconds') без таймзоны: "2025-04-15T10:30:45"

    private fun isoFormat(date: Date): String {
        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
        sdf.timeZone = TimeZone.getDefault()  // как datetime.now() без tz
        return sdf.format(date)
    }

    private fun parseIso(s: String): Date? {
        return try {
            val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            sdf.timeZone = TimeZone.getDefault()
            sdf.parse(s)
        } catch (e: Exception) {
            null
        }
    }

    private fun monthsWord(n: Int): String {
        if (n % 100 in 11..19) return "месяцев"
        return when (n % 10) {
            1 -> "месяц"
            2, 3, 4 -> "месяца"
            else -> "месяцев"
        }
    }

    private fun sha256Hex(s: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(s.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    // ─── Файл лицензии ──────────────────────────────────────────────

    private fun licenseFile(context: Context): File =
        File(context.filesDir, LICENSE_FILENAME)

    // ─── Активация ──────────────────────────────────────────────────

    /**
     * Активирует ключ. Возвращает (true, сообщение) или (false, ошибка).
     *
     * @param expectedSubject если задан — ключ должен быть для этого предмета
     *                        (для однопредметных flavor-сборок).
     *                        "all" / null — любой предмет.
     */
    fun activateKey(
        context: Context,
        keyStr: String,
        expectedSubject: String? = null
    ): Pair<Boolean, String> {
        val (payload, err) = validateKey(keyStr, context)
        if (payload == null) return false to err

        // Проверка соответствия предмета для flavor-сборки
        if (expectedSubject != null && expectedSubject != "all"
            && payload.subject != expectedSubject) {
            return false to "Ключ для предмета «${payload.subject}», " +
                    "а это приложение для «$expectedSubject»."
        }

        val deviceId = getDeviceId(context)
        val now = Date()
        val expires = Date(now.time + payload.durationMonths.toLong() * 30L * 24L * 3600L * 1000L)

        val data = JSONObject().apply {
            put("key_hash", sha256Hex(keyStr.uppercase()))
            put("device_id", deviceId)
            put("subject", payload.subject)
            put("subject_idx", payload.subjectIdx)
            put("client_id", payload.clientId)
            put("duration_months", payload.durationMonths)
            put("activated_at", isoFormat(now))
            put("expires_at", isoFormat(expires))
            put("last_check", isoFormat(now))
            put("version", LICENSE_VERSION)
        }

        return try {
            val encrypted = encryptLicense(data, deviceId)
            licenseFile(context).writeBytes(encrypted)
            true to "Активация успешна! Лицензия действительна " +
                    "${payload.durationMonths} ${monthsWord(payload.durationMonths)}."
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка сохранения лицензии", e)
            false to "Ошибка сохранения лицензии: ${e.message}"
        }
    }

    // ─── Проверка лицензии ──────────────────────────────────────────

    fun getLicenseStatus(context: Context): LicenseStatus {
        val file = licenseFile(context)
        if (!file.exists()) {
            return LicenseStatus(false, "Лицензия не найдена")
        }

        val raw = try {
            file.readBytes()
        } catch (e: Exception) {
            return LicenseStatus(false, "Ошибка чтения файла лицензии")
        }

        val deviceId = getDeviceId(context)
        val data = decryptLicense(raw, deviceId)
            ?: return LicenseStatus(false, "Лицензия повреждена или принадлежит другому устройству")

        if (data.optInt("version") != LICENSE_VERSION) {
            return LicenseStatus(false, "Устаревший формат лицензии")
        }
        if (data.optString("device_id") != deviceId) {
            return LicenseStatus(false, "Лицензия привязана к другому устройству")
        }

        val now = Date()

        // Защита от перевода часов назад
        val lastCheckStr = data.optString("last_check", "")
        val lastCheck = parseIso(lastCheckStr)
        if (lastCheck != null) {
            val driftMs = lastCheck.time - now.time
            if (driftMs > MAX_CLOCK_DRIFT_HOURS * 3600L * 1000L) {
                return LicenseStatus(false,
                    "Обнаружено изменение системных часов. Обратитесь в поддержку.")
            }
        }

        val expiresAtStr = data.optString("expires_at", "")
        val expiresAt = parseIso(expiresAtStr)
            ?: return LicenseStatus(false, "Повреждены данные лицензии")

        if (now.after(expiresAt)) {
            return LicenseStatus(false, "Срок действия лицензии истёк",
                expiresAt = expiresAtStr)
        }

        val daysLeft = ((expiresAt.time - now.time) / (24L * 3600L * 1000L)).toInt()

        // Обновляем last_check
        try {
            data.put("last_check", isoFormat(now))
            file.writeBytes(encryptLicense(data, deviceId))
        } catch (e: Exception) {
            Log.w(TAG, "Не удалось обновить last_check", e)
        }

        return LicenseStatus(
            valid = true,
            reason = "OK",
            subject = data.optString("subject", null),
            expiresAt = expiresAtStr,
            daysLeft = daysLeft
        )
    }

    fun isActivated(context: Context): Boolean = getLicenseStatus(context).valid

    fun getActivatedSubject(context: Context): String? {
        val s = getLicenseStatus(context)
        return if (s.valid) s.subject else null
    }
}
