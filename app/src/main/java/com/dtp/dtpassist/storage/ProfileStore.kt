package com.dtp.dtpassist.storage

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.map

val Context.profileDataStore by preferencesDataStore("profile")

data class UserProfile(
    val login: String = "",
    val firstName: String = "",
    val lastName: String = "",
    val middleName: String = "",
    val phone: String = "",
    val insurancePhone: String = "",
    val email: String = "",
    val passportIssuedBy: String = "",
    val passportIssueDate: String = "",
    val passportUnitCode: String = "",
    val passportSeriesNumber: String = "",
    val driverLicense: String = "",
    val sts: String = "",
    val diagnosticCard: String = "",
    val car: String = "",
    val plate: String = "",
    val osago: String = "",
)

class ProfileStore(private val context: Context) {
    private val keys = listOf(
        "login",
        "first",
        "last",
        "middle",
        "phone",
        "insurance_phone",
        "email",
        "passport_issued_by",
        "passport_issue_date",
        "passport_unit_code",
        "passport_series_number",
        "driver_license",
        "sts",
        "diagnostic_card",
        "car",
        "plate",
        "osago",
    ).map { stringPreferencesKey(it) }
    val profile = context.profileDataStore.data.map {
        UserProfile(
            login = it[keys[0]].orEmpty(),
            firstName = it[keys[1]].orEmpty(),
            lastName = it[keys[2]].orEmpty(),
            middleName = it[keys[3]].orEmpty(),
            phone = it[keys[4]].orEmpty(),
            insurancePhone = it[keys[5]].orEmpty(),
            email = it[keys[6]].orEmpty(),
            passportIssuedBy = it[keys[7]].orEmpty(),
            passportIssueDate = it[keys[8]].orEmpty(),
            passportUnitCode = it[keys[9]].orEmpty(),
            passportSeriesNumber = it[keys[10]].orEmpty(),
            driverLicense = it[keys[11]].orEmpty(),
            sts = it[keys[12]].orEmpty(),
            diagnosticCard = it[keys[13]].orEmpty(),
            car = it[keys[14]].orEmpty(),
            plate = it[keys[15]].orEmpty(),
            osago = it[keys[16]].orEmpty(),
        )
    }

    suspend fun save(p: UserProfile) = context.profileDataStore.edit {
        it[keys[0]] = p.login
        it[keys[1]] = p.firstName
        it[keys[2]] = p.lastName
        it[keys[3]] = p.middleName
        it[keys[4]] = p.phone
        it[keys[5]] = p.insurancePhone
        it[keys[6]] = p.email
        it[keys[7]] = p.passportIssuedBy
        it[keys[8]] = p.passportIssueDate
        it[keys[9]] = p.passportUnitCode
        it[keys[10]] = p.passportSeriesNumber
        it[keys[11]] = p.driverLicense
        it[keys[12]] = p.sts
        it[keys[13]] = p.diagnosticCard
        it[keys[14]] = p.car
        it[keys[15]] = p.plate
        it[keys[16]] = p.osago
    }
}
