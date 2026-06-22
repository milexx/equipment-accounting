# Исследование Юлы Как Источника Цен

Дата: 2026-06-21

## Цель

Проверить, можно ли использовать Юлу как дополнительный экспериментальный рыночный источник для модуля оценщика после того, как Avito начал возвращать `HTTP 403` по всем отслеживаемым позициям на Day 4.

## Краткий Вывод

Юла технически доступна с текущего сервера и может возвращать публичные данные объявлений через свой каталог GraphQL.

Это еще не делает Юлу стабильным производственным источником. Но она лучше подходит как второй ручной экспериментальный источник, чем повтор заблокированных запусков Avito, потому что первый контролируемый запрос вернул `HTTP 200` и данные объявлений с ценами.

## Что Проверено

Прямые HTTP-проверки:

- `https://youla.ru/` вернул `HTTP 200`.
- `https://www.youla.ru/` перенаправил на `https://youla.ru/`.
- `https://m.youla.ru/` перенаправил на `https://youla.io/`.
- `https://youla.ru/moskva?q=Lenovo%20ThinkPad%20T14` вернул `HTTP 200`.
- `https://youla.ru/all?q=Lenovo%20ThinkPad%20T14` вернул `HTTP 200`.

HTML содержит `window.__YOULA_STATE__` со следующими данными:

- `apiUri: https://api.youla.ru`
- `apiFederationUri: https://api-gw.youla.ru/graphql`
- `apiProxyUri: /web-api`
- `apiClientId: web/3`
- публичный анонимный `uid`
- данные геолокации Москвы

SSR-состояние не содержит сами объявления. Данные объявлений загружаются фронтендом через Apollo GraphQL.

## Конечная Точка GraphQL

В JS-бандлах Юлы найден релевантный фронтенд-запрос:

```graphql
query catalogProductsBoard(
  $sort: Sort,
  $attributes: [AttributeItem!],
  $location: LocationInput,
  $cursor: Cursor!,
  $search: String,
  $datePublished: DateInput
) {
  feed(
    input: {
      sort: $sort,
      attributes: $attributes,
      location: $location,
      search: $search,
      datePublished: $datePublished
    },
    after: $cursor
  ) {
    items {
      ... on BannerItem {
        type
        banner {
          title
          description
          buttonTitle
          imageURL
        }
      }
      ... on PromotedProductItem {
        product: productPromoted {
          id
          categoryId: category
          subcategoryId: subcategory
          price {
            origPrice { price }
            realPrice { price }
            realPriceText
            discount
          }
          url
          images { id num url }
          name
          location {
            cityName
            city
            addressText
            description
            latitude
            longitude
          }
          distanceText
          isPromoted
          favorite { enabled }
          deliveryAvailable
          paymentAvailable
          branding { imageUrl rating }
          salaryText
        }
        productAnalytics { promotionType }
      }
      ... on ProductItem {
        product {
          id
          categoryId: category
          subcategoryId: subcategory
          price {
            origPrice { price }
            realPrice { price }
            realPriceText
            discount
          }
          url
          images { id num url }
          name
          location {
            cityName
            city
            addressText
            description
            latitude
            longitude
          }
          distanceText
          isPromoted
          favorite { enabled }
          deliveryAvailable
          paymentAvailable
          branding { imageUrl rating }
          salaryText
        }
        productAnalytics { promotionType }
      }
    }
    pageInfo {
      cursor
      hasNextPage
      personalSearchId
      productsAnalytics { searchId }
    }
  }
}
```

Контрольный запрос:

- конечная точка: `https://api-gw.youla.ru/graphql`
- операция: `catalogProductsBoard`
- поиск: `Lenovo ThinkPad T14`
- геолокация: координаты Москвы из SSR-состояния
- результат: `HTTP 200`
- данные: карточки товаров с `id`, `name`, `price.origPrice.price`, `price.realPrice.price`, `price.realPriceText`, `url`, `location.cityName`, `distanceText`
- `pageInfo` вернул cursor и `hasNextPage: true`

Проверка ручного POC-скрипта:

- команда: `python3 research/youla-source-poc/fetch_youla_catalog.py 'Lenovo ThinkPad T14'`
- результат: `HTTP 200`
- нормализованный статус: `ok`
- нормализованное количество: `30`
- первый пример нормализации цены: `4500000 -> 45000.0`

## Важная Структура Данных

Наблюдаемая единица цены — целые копейки, не рубли:

- `4500000` соответствует `45 000 ₽`.
- `13500000` соответствует `135 000 ₽`.
- `799000` соответствует `7 990 ₽`.

Для нормализации:

- хранить исходную цену источника как она пришла;
- хранить нормализованные рубли как `price / 100`;
- сохранять `realPriceText` для аудита и отладки.

## Качество Источника

Плюсы:

- публичная конечная точка вернула `HTTP 200` с того же сервера, где Avito вернул `HTTP 403`;
- для проверенного запроса каталога не понадобился вход;
- данные уже содержат структурированные цены, название, URL, город и расстояние;
- есть пагинация через `pageInfo.cursor`.

Риски:

- это внутренний веб-API GraphQL, а не стабильный публичный партнерский API;
- заголовки запроса и схема могут измениться без предупреждения;
- текущий первый запрос был только проверкой доступности, а не многодневным тестом устойчивости;
- релевантность поиска широкая: запрос `Lenovo ThinkPad T14` вернул часть нерелевантных моделей Lenovo, поэтому существующий фильтр релевантности все еще нужен;
- покрытие Юлы по части корпоративного оборудования может быть слабее, чем у Avito.

## Решение

Рекомендуемое следующее состояние: `youla_manual_source_poc`.

Использовать Юлу как ручной экспериментальный источник за той же границей состояния источника, что и Avito:

- без планировщика;
- без повторного фонового обхода;
- один контролируемый запуск на тестовое окно;
- сохранять каждый запуск как снимок со статусом источника;
- не считать успешный ответ Юлы доказательством производственной надежности.

## Следующие Шаги

1. Добавить небольшой ручной POC-скрипт Юлы, который выполняет один запрос и выдает нормализованный JSON.
2. Один раз запустить его по текущим отслеживаемым позициям с консервативными паузами.
3. Сравнить релевантность Юлы и медианные цены с последними успешными снимками Avito.
4. Если источник полезен, добавить снимки `source = youla` в модель ценовой истории без изменения контракта интерфейса.
5. Оставить Avito в состоянии `manual_experimental` / `blocked_recently`; не повторять заблокированный Avito в тот же день.
