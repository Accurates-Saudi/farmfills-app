from datetime import datetime
from django.db import connection
from django.utils import timezone

# Use this function to get a specific date's (default: today) delivery list
def daily_delivery_query(date=None, route_id=None):
    # date can be a 'YYYY-MM-DD' string or a date object (get_order_list passes a date)
    today = str(date or timezone.localdate())
    weekday = datetime.strptime(today, '%Y-%m-%d').strftime('%a').lower()  # 'mon', 'tue', etc.
    weekly_field = {
        'mon': 'weekly_mon',
        'tue': 'weekly_tue',
        'wed': 'weekly_wed',
        'thu': 'weekly_thu',
        'fri': 'weekly_fri',
        'sat': 'weekly_sat',
        'sun': 'weekly_sun'
    }[weekday]

    # Filter by route if provided, if it's assigned to another route, filter by that route
    route_clause = (
        f"WHERE ra.to_route_id = {route_id} "
        f"OR (ra.to_route_id IS NULL AND r.id = {route_id})"
        if route_id else ""
    )

    results = []
    with connection.cursor() as cursor:
        query = f"""
            WITH user_costs AS (
                SELECT
                    u.id AS user_id,
                    u.delivery_name,
                    u.mobile,
                    u.balance,
                    u.user_type_id,
                    ut.suspend,
                    p.price + ut.price_variation AS cost,
                    sf.name AS delivery_boy,
                    r.name AS route_name,
                    r.id AS route_id,
                    a.name AS area_name,
                    CASE 
                        WHEN ra.id IS NOT NULL THEN TRUE
                        ELSE FALSE
                    END AS assigned,
                    CASE
                        --- Priority 1: ExtraLess
                        WHEN el.id IS NOT NULL THEN el.quantity * 2

                        --- Priority 2: Vacation
                        WHEN v.id IS NOT NULL THEN 0

                        --- Priority 3: Subscription
                        WHEN s.id IS NOT NULL THEN
                            CASE

                                --- Day1 and Day2 in daily, fallback to Day1 if Day2 is 0
                                WHEN s.sub_type = 'daily' THEN 
                                    CASE 
                                        WHEN MOD((DATE '{today}' - s.start_date), 2) = 0 THEN COALESCE(s.daily_day1, 0)
                                        ELSE COALESCE(NULLIF(s.daily_day2, 0), s.daily_day1, 0)
                                    END

                                --- Alternate: alternate quantity on even days, 0 on odd days
                                WHEN s.sub_type = 'alternate' THEN 
                                    CASE 
                                        WHEN MOD((DATE '{today}' - s.start_date), 2) = 0 THEN COALESCE(s.alternate_quantity, 0)
                                        ELSE 0
                                    END

                                --- Weekly: weekly quantity for the specific day
                                WHEN s.sub_type = 'weekly' THEN COALESCE(s.{weekly_field}, 0)

                                -- Custom interval
                                WHEN s.sub_type = 'custom' THEN 
                                    CASE 
                                        WHEN MOD(DATE '{today}' - s.start_date, s.custom_interval) = 0 THEN COALESCE(s.custom_quantity, 0)
                                        ELSE 0
                                    END

                                ELSE 0
                            END * 2                           
                        ELSE 0
                    END AS total_quantity

                FROM users_user u

                LEFT OUTER JOIN users_extraless el
                    ON el.user_id = u.id
                    AND el.start_date <= DATE '{today}'
                    AND el.end_date >= DATE '{today}'
                LEFT OUTER JOIN users_vacation v
                    ON v.user_id = u.id
                    AND v.start_date <= DATE '{today}'
                    AND (v.end_date IS NULL OR v.end_date >= DATE '{today}')
                LEFT OUTER JOIN users_subscription s
                    ON s.user_id = u.id
                    AND s.start_date <= DATE '{today}'
                    AND (s.end_date IS NULL OR s.end_date >= DATE '{today}')
                LEFT OUTER JOIN users_product p
                    ON p.id = 1
                LEFT OUTER JOIN users_usertype ut
                    ON u.user_type_id = ut.id
                LEFT OUTER JOIN users_routeassign ra
                    ON ra.user_id = u.id
                LEFT OUTER JOIN users_route r
                    ON (ra.id IS NOT NULL AND ra.to_route_id = r.id) OR (ra.id IS NULL AND u.route_id = r.id)
                LEFT OUTER JOIN users_staff sf
                    ON sf.route_id = r.id
                LEFT OUTER JOIN users_area a
                    ON a.id = r.area_id

                {route_clause}

                ORDER BY u.route_order
            )

            SELECT user_id, delivery_name, mobile, user_type_id, delivery_boy, route_name, route_id, area_name, assigned, total_quantity, cost
            FROM user_costs
            --- Only include users with sufficient balance when their account type is to be suspended
            WHERE total_quantity != 0 AND (suspend = FALSE OR balance >= cost * total_quantity)
        """
        cursor.execute(query)
        results = cursor.fetchall()

    return results
