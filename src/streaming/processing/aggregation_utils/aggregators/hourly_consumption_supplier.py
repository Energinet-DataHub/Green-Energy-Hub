from pyspark.sql import DataFrame
from pyspark.sql.functions import col
from processing.codelists import MarketEvaluationPointType, SettlementMethod


class HourlyConsumptionSupplierAggregator:

    @staticmethod
    def aggregate(df: DataFrame):
        return df \
            .filter(col("MarketEvaluationPointType") == MarketEvaluationPointType.consumption.value) \
            .filter(col("SettlementMethod") == SettlementMethod.non_profiled.value) \
            .groupBy("MeteringGridArea_Domain_mRID",
                     "EnergySupplier_MarketParticipant_mRID",
                     "BalanceResponsibleParty_MarketParticipant_mRID") \
            .sum("Quantity") \
            .withColumnRenamed("sum(Quantity)", "sum_quantity") \
            .orderBy("MeteringGridArea_Domain_mRID",
                     "EnergySupplier_MarketParticipant_mRID",
                     "BalanceResponsibleParty_MarketParticipant_mRID")
